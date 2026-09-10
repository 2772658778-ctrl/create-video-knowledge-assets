from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path

from pydantic import ValidationError


SCRIPTS_DIR = Path(__file__).resolve().parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from vka.acquire import metadata_command, subtitle_command
from vka.digest import DEFAULT_WINDOW_MS, build_timeline_digest
from vka.frames import plan_candidate_timestamps
from vka.inputs import (
    archive_local_video,
    describe_local_video,
    normalize_bilibili_url,
    sanitize_acquired_metadata,
    validate_bilibili_part_selection,
)
from vka.knowledge_gate import validate_asset_knowledge
from vka.lifecycle import execute_l2_cleanup, plan_l2_cleanup, verify_asset
from vka.preflight import inspect_commands
from vka.preflight import find_command
from vka.profiles import (
    get_profile,
    reproject_profile_documents,
    write_profile_selection,
    write_projection_plan,
)
from vka.projection_plan import validate_projection_plan
from vka.qa_contract import GroundedAnswer
from vka.qa_external import EXTERNAL_EVIDENCE_PATH, read_external_evidence, register_external_evidence
from vka.qa_index import build_qa_index
from vka.qa_planning import build_answer_plan
from vka.qa_retrieval import retrieve_question
from vka.qa_topology import build_qa_topology
from vka.qa_validation import validate_grounded_answer
from vka.quality import (
    validate_course_document_quality,
    validate_document_image_files,
    validate_document_quality,
)
from vka.render_latex import render_course_tex, render_document_tex
from vka.render_html import render_course_html, render_document_html
from vka.render_markdown import render_course_markdown, render_document_markdown
from vka.store import AssetStore
from vka.teaching_outline import validate_teaching_outline
from vka.transcript import parse_srt_as_evidence
from vka.transcript_repair import (
    apply_transcript_repairs,
    build_asr_repair_prompt,
    suggest_asr_repairs,
)


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args) or 0
    except ValueError as exc:
        parser.exit(1, f"error: {exc}\n")
    except OSError as exc:
        parser.exit(1, f"error: {exc}\n")
    return 0


_STAGE_NAME_PATTERN = re.compile(
    r"^(source|evidence|knowledge|content|views|outputs)(/[a-z0-9][a-z0-9-]*){0,2}$"
)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="vka")
    subparsers = parser.add_subparsers(dest="command", required=True)

    preflight = subparsers.add_parser("preflight")
    preflight.add_argument("--commands", nargs="+", required=True)
    preflight.set_defaults(func=_run_preflight)

    create_asset = subparsers.add_parser(
        "create-asset",
        help="create an asset directory and manifest from a normalized input descriptor",
    )
    create_asset.add_argument("--assets-root", required=True)
    create_asset.add_argument(
        "--input",
        required=True,
        help="normalized input descriptor JSON, for example the output of normalize-bilibili-url",
    )
    create_asset.add_argument("--asset-id", help="defaults to the descriptor asset_id")
    create_asset.add_argument("--config", help="optional JSON object of run configuration")
    create_asset.add_argument(
        "--tool-version",
        action="append",
        default=[],
        dest="tool_versions",
        help="repeat as name=value, for example asr_backend=faster-whisper",
    )
    create_asset.set_defaults(func=_run_create_asset)

    describe_local = subparsers.add_parser("describe-local-video")
    describe_local.add_argument("--input", required=True)
    describe_local.add_argument(
        "--existing-identity",
        help="JSON manifest or source descriptor to validate before using its asset ID",
    )
    describe_local.add_argument(
        "--archive-l1-source-dir",
        help="copy into this source/video directory only for explicit L1 retention",
    )
    describe_local.set_defaults(func=_run_describe_local_video)

    normalize_bilibili = subparsers.add_parser("normalize-bilibili-url")
    normalize_bilibili.add_argument("--url", required=True)
    normalize_bilibili.set_defaults(func=_run_normalize_bilibili_url)

    normalize_srt = subparsers.add_parser("normalize-srt")
    normalize_srt.add_argument("--input", required=True)
    normalize_srt.add_argument("--output", required=True)
    normalize_srt.add_argument("--acquisition", choices=("cc", "asr"), required=True)
    normalize_srt.add_argument(
        "--id-prefix",
        default="",
        help="prefix raw evidence ids, for example raw- when writing timeline.raw.jsonl",
    )
    normalize_srt.set_defaults(func=_run_normalize_srt)

    timeline_digest = subparsers.add_parser(
        "timeline-digest",
        help="write a compact reading view of a canonical timeline",
    )
    timeline_digest.add_argument("--timeline", required=True)
    timeline_digest.add_argument("--output", required=True)
    timeline_digest.add_argument(
        "--window-ms",
        type=int,
        default=DEFAULT_WINDOW_MS,
        help="group rows into windows of this length",
    )
    timeline_digest.set_defaults(func=_run_timeline_digest)

    repair_prompt = subparsers.add_parser("build-repair-prompt")
    repair_prompt.add_argument("--timeline", required=True)
    repair_prompt.add_argument("--output", required=True)
    repair_prompt.add_argument("--title")
    repair_prompt.set_defaults(func=_run_build_repair_prompt)

    suggest_repairs = subparsers.add_parser("suggest-repairs")
    suggest_repairs.add_argument("--timeline", required=True)
    suggest_repairs.add_argument("--output", required=True)
    suggest_repairs.set_defaults(func=_run_suggest_repairs)

    apply_repairs = subparsers.add_parser("apply-transcript-repairs")
    apply_repairs.add_argument("--timeline", required=True)
    apply_repairs.add_argument("--repairs", required=True)
    apply_repairs.add_argument("--output", required=True)
    apply_repairs.add_argument(
        "--parent-prefix",
        default=None,
        help=(
            "strip this prefix from input ids and record the raw id in parent_ids; "
            "use the same value passed to normalize-srt --id-prefix"
        ),
    )
    apply_repairs.set_defaults(func=_run_apply_transcript_repairs)

    acquire_metadata = subparsers.add_parser("acquire-metadata")
    acquire_metadata.add_argument("--url", required=True)
    acquire_metadata.add_argument("--cookie-file")
    acquire_metadata.add_argument("--output", required=True)
    acquire_metadata.set_defaults(func=_run_acquire_metadata)

    acquire_subs = subparsers.add_parser("acquire-subs")
    acquire_subs.add_argument("--url", required=True)
    acquire_subs.add_argument("--cookie-file")
    acquire_subs.add_argument("--output-template", required=True)
    acquire_subs.set_defaults(func=_run_acquire_subs)

    plan_frames = subparsers.add_parser("plan-frames")
    plan_frames.add_argument("--start-ms", type=int, required=True)
    plan_frames.add_argument("--end-ms", type=int, required=True)
    plan_frames.add_argument("--interval-ms", type=int, required=True)
    plan_frames.set_defaults(func=_run_plan_frames)

    verify_asset_parser = subparsers.add_parser("verify-asset")
    verify_asset_parser.add_argument("--asset", required=True)
    verify_asset_parser.set_defaults(func=_run_verify_asset)

    validate_knowledge = subparsers.add_parser(
        "validate-knowledge",
        help="check knowledge reference closure and evidence-strength honesty",
    )
    validate_knowledge.add_argument("--asset", required=True)
    validate_knowledge.set_defaults(func=_run_validate_knowledge)

    complete_stage = subparsers.add_parser(
        "complete-stage",
        help="record a completed stage and the SHA-256 of each of its outputs",
    )
    complete_stage.add_argument("--asset", required=True)
    complete_stage.add_argument(
        "--stage",
        required=True,
        help="stage name, for example source, evidence, knowledge, views/<profile>",
    )
    complete_stage.add_argument(
        "--output",
        action="append",
        required=True,
        dest="outputs",
        help="repeat for every stage output; paths are relative to the asset root",
    )
    complete_stage.add_argument("--schema-version", default=None)
    complete_stage.set_defaults(func=_run_complete_stage)

    cleanup_l2 = subparsers.add_parser("cleanup-l2")
    cleanup_l2.add_argument("--asset", required=True)
    cleanup_mode = cleanup_l2.add_mutually_exclusive_group(required=True)
    cleanup_mode.add_argument("--dry-run", action="store_true")
    cleanup_mode.add_argument("--apply", action="store_true")
    cleanup_l2.set_defaults(func=_run_cleanup_l2)

    select_profile = subparsers.add_parser("select-profile", aliases=["route-profile"])
    select_profile.add_argument("--asset", required=True)
    select_profile.add_argument("--profile")
    select_profile.add_argument("--intent")
    select_profile.add_argument("--format", dest="formats", action="append", choices=("md", "html", "tex", "pdf"))
    select_profile.set_defaults(func=_run_select_profile)

    reproject_profile = subparsers.add_parser("reproject-profile")
    reproject_profile.add_argument("--asset", required=True)
    reproject_profile.add_argument("--profile", required=True)
    reproject_profile.add_argument("--document", required=True)
    reproject_profile.set_defaults(func=_run_reproject_profile)

    validate_projection_plan_parser = subparsers.add_parser("validate-projection-plan")
    validate_projection_plan_parser.add_argument("--input", required=True)
    validate_projection_plan_parser.add_argument("--profile", required=True)
    validate_projection_plan_parser.set_defaults(func=_run_validate_projection_plan)

    write_projection_plan_parser = subparsers.add_parser("write-projection-plan")
    write_projection_plan_parser.add_argument("--asset", required=True)
    write_projection_plan_parser.add_argument("--profile", required=True)
    write_projection_plan_parser.add_argument("--input", required=True)
    write_projection_plan_parser.set_defaults(func=_run_write_projection_plan)

    render_course = subparsers.add_parser("render-course")
    render_course.add_argument("--input", required=True)
    render_course.add_argument("--output", required=True)
    render_course.add_argument(
        "--quality-floor",
        choices=("p1", "smoke"),
        default="p1",
        help="use smoke only for renderer tests or minimal layout checks",
    )
    render_course.set_defaults(func=_run_render_course)

    render_markdown = subparsers.add_parser("render-markdown")
    render_markdown.add_argument("--input", required=True)
    render_markdown.add_argument("--output", required=True)
    render_markdown.add_argument(
        "--quality-floor",
        choices=("p1", "smoke"),
        default="smoke",
        help="use p1 before treating Markdown as a deliverable",
    )
    render_markdown.set_defaults(func=_run_render_markdown)

    render_html = subparsers.add_parser("render-html")
    render_html.add_argument("--input", required=True)
    render_html.add_argument("--output", required=True)
    render_html.add_argument(
        "--quality-floor",
        choices=("p1", "smoke"),
        default="smoke",
        help="use p1 before treating HTML as a deliverable",
    )
    render_html.set_defaults(func=_run_render_html)

    validate_document = subparsers.add_parser("validate-document")
    validate_document.add_argument("--input", required=True)
    validate_document.add_argument("--profile", required=True)
    validate_document.set_defaults(func=_run_validate_document)

    render_document = subparsers.add_parser("render-document")
    render_document.add_argument("--input", required=True)
    render_document.add_argument("--output", required=True)
    render_document.add_argument("--profile", required=True)
    render_document.add_argument("--format", required=True, choices=("md", "html", "tex"))
    render_document.set_defaults(func=_run_render_document)

    validate_outline = subparsers.add_parser("validate-teaching-outline")
    validate_outline.add_argument("--input", required=True)
    validate_outline.set_defaults(func=_run_validate_teaching_outline)

    compile_pdf = subparsers.add_parser("compile-pdf")
    compile_pdf.add_argument("--tex", required=True)
    compile_pdf.add_argument("--output-directory", required=True)
    compile_pdf.set_defaults(func=_run_compile_pdf)

    build_qa_index_parser = subparsers.add_parser("build-qa-index")
    build_qa_index_parser.add_argument("--asset", required=True)
    build_qa_index_parser.add_argument("--profile", choices=("course-notes",), required=True)
    build_qa_index_parser.set_defaults(func=_run_build_qa_index)

    build_qa_topology_parser = subparsers.add_parser("build-qa-topology")
    build_qa_topology_parser.add_argument("--asset", required=True)
    build_qa_topology_parser.add_argument(
        "--profile", choices=("course-notes",), required=True
    )
    build_qa_topology_parser.set_defaults(func=_run_build_qa_topology)

    retrieve_qa = subparsers.add_parser("retrieve-qa")
    retrieve_qa.add_argument("--asset", required=True)
    retrieve_qa.add_argument("--question", required=True)
    retrieve_qa.add_argument(
        "--mode",
        choices=("video_only", "video_plus_context", "explore"),
        default="video_only",
    )
    retrieve_qa.add_argument("--limit", type=int, default=8)
    retrieve_qa.set_defaults(func=_run_retrieve_qa)

    plan_qa = subparsers.add_parser("plan-qa")
    plan_qa.add_argument("--input", required=True)
    plan_qa.set_defaults(func=_run_plan_qa)

    validate_answer = subparsers.add_parser("validate-answer")
    validate_answer.add_argument("--asset", required=True)
    validate_answer.add_argument("--input", required=True)
    validate_answer.set_defaults(func=_run_validate_answer)

    register_external = subparsers.add_parser("register-external-evidence")
    register_external.add_argument("--asset", required=True)
    register_external.add_argument("--input", required=True)
    register_external.set_defaults(func=_run_register_external_evidence)

    validate_external = subparsers.add_parser("validate-external-evidence")
    validate_external.add_argument("--asset", required=True)
    validate_external.set_defaults(func=_run_validate_external_evidence)

    return parser


def _run_preflight(args: argparse.Namespace) -> None:
    report = inspect_commands(args.commands)
    print(json.dumps(report, ensure_ascii=False))


def _run_create_asset(args: argparse.Namespace) -> int:
    try:
        descriptor = _read_json_object(Path(args.input), "input descriptor")
        asset_id = args.asset_id or descriptor.get("asset_id")
        if not isinstance(asset_id, str) or not asset_id:
            raise ValueError("asset id must come from --asset-id or the input descriptor")
        config = (
            _read_json_object(Path(args.config), "config") if args.config else {}
        )
        tool_versions: dict[str, str] = {}
        for item in args.tool_versions:
            name, separator, value = item.partition("=")
            if not separator or not name or not value:
                raise ValueError(f"tool version must use name=value: {item}")
            tool_versions[name] = value
        store = AssetStore.create(
            Path(args.assets_root),
            asset_id,
            descriptor,
            config=config,
            tool_versions=tool_versions,
        )
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        sys.stderr.write(f"error: failed to create asset: {exc}\n")
        return 1
    print(json.dumps({"asset_id": asset_id, "asset_root": str(store.root)}, ensure_ascii=False))
    return 0


def _run_describe_local_video(args: argparse.Namespace) -> None:
    existing_identity = None
    if args.existing_identity:
        existing_identity = json.loads(Path(args.existing_identity).read_text(encoding="utf-8"))
        if not isinstance(existing_identity, dict):
            raise ValueError("existing asset identity must be a JSON object")
    if existing_identity is None:
        descriptor = describe_local_video(Path(args.input))
    else:
        descriptor = describe_local_video(
            Path(args.input),
            existing_identity=existing_identity,
        )
    if args.archive_l1_source_dir:
        archived_path = archive_local_video(
            args.input,
            args.archive_l1_source_dir,
            retention="L1",
        )
        descriptor["archived_path"] = str(archived_path)
    print(json.dumps(descriptor, ensure_ascii=False))


def _run_normalize_bilibili_url(args: argparse.Namespace) -> None:
    print(json.dumps(normalize_bilibili_url(args.url), ensure_ascii=False))


def _run_normalize_srt(args: argparse.Namespace) -> None:
    input_path = Path(args.input)
    output_path = Path(args.output)
    rows = parse_srt_as_evidence(
        input_path.read_text(encoding="utf-8"),
        acquisition=args.acquisition,
        id_prefix=args.id_prefix,
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as file:
        for row in rows:
            file.write(json.dumps(row, ensure_ascii=False))
            file.write("\n")


def _run_build_repair_prompt(args: argparse.Namespace) -> int:
    try:
        rows = _read_jsonl(Path(args.timeline))
        prompt = build_asr_repair_prompt(rows, title=args.title)
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(prompt, encoding="utf-8")
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        sys.stderr.write(f"error: failed to build ASR repair prompt: {exc}\n")
        return 1
    return 0


def _run_timeline_digest(args: argparse.Namespace) -> int:
    try:
        rows = _read_jsonl(Path(args.timeline))
        digest = build_timeline_digest(rows, window_ms=args.window_ms)
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(digest, encoding="utf-8")
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        sys.stderr.write(f"error: failed to build timeline digest: {exc}\n")
        return 1
    print(
        json.dumps(
            {
                "timeline": args.timeline,
                "output": args.output,
                "rows": len(rows),
                "characters": len(digest),
            },
            ensure_ascii=False,
        )
    )
    return 0


def _run_suggest_repairs(args: argparse.Namespace) -> int:
    try:
        rows = _read_jsonl(Path(args.timeline))
        repairs = suggest_asr_repairs(rows)
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(repairs, ensure_ascii=False, indent=2), encoding="utf-8")
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        sys.stderr.write(f"error: failed to suggest ASR repairs: {exc}\n")
        return 1
    return 0


def _run_apply_transcript_repairs(args: argparse.Namespace) -> int:
    try:
        rows = _read_jsonl(Path(args.timeline))
        repairs = json.loads(Path(args.repairs).read_text(encoding="utf-8"))
        repaired_rows = apply_transcript_repairs(
            rows,
            repairs,
            parent_prefix=args.parent_prefix,
        )
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with output_path.open("w", encoding="utf-8") as file:
            for row in repaired_rows:
                file.write(json.dumps(row, ensure_ascii=False))
                file.write("\n")
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        sys.stderr.write(f"error: failed to apply ASR repairs: {exc}\n")
        return 1
    return 0


def _run_acquire_metadata(args: argparse.Namespace) -> int:
    cookie_file = _validated_cookie_file(args.cookie_file)
    output_path = Path(args.output)
    source = normalize_bilibili_url(args.url)
    try:
        result = subprocess.run(
            metadata_command(str(source["canonical_url"]), cookie_file=cookie_file),
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
    except subprocess.CalledProcessError as exc:
        _write_process_error("failed to acquire metadata", exc)
        return exc.returncode or 1
    except OSError as exc:
        _write_run_error(exc)
        return 1

    try:
        metadata = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        sys.stderr.write(f"error: invalid metadata JSON: {exc}\n")
        return 1
    if not isinstance(metadata, dict):
        sys.stderr.write("error: invalid metadata JSON: expected an object\n")
        return 1
    try:
        validate_bilibili_part_selection(source, metadata)
    except ValueError as exc:
        sys.stderr.write(f"error: {exc}\n")
        return 1

    try:
        sanitized_metadata = sanitize_acquired_metadata(metadata)
    except ValueError:
        sys.stderr.write("error: failed to sanitize metadata\n")
        return 1
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(sanitized_metadata, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )
    return 0


def _run_acquire_subs(args: argparse.Namespace) -> int:
    cookie_file = _validated_cookie_file(args.cookie_file)
    output_template = Path(args.output_template)
    output_directory = output_template.parent
    before = _srt_files(output_directory)
    source = normalize_bilibili_url(args.url)
    if not _validate_unselected_bilibili_source(source, cookie_file=cookie_file):
        return 1
    try:
        subprocess.run(
            subtitle_command(
                str(source["canonical_url"]),
                args.output_template,
                cookie_file=cookie_file,
            ),
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
    except subprocess.CalledProcessError as exc:
        _write_process_error("failed to acquire subtitles", exc)
        return exc.returncode or 1
    except OSError as exc:
        _write_run_error(exc)
        return 1

    after = _srt_files(output_directory)
    if not after - before:
        sys.stderr.write(
            "error: no subtitle SRT files were downloaded; "
            "use ASR when reliable CC subtitles are unavailable\n"
        )
        return 1

    return 0


def _validate_unselected_bilibili_source(
    source: Mapping[str, object], *, cookie_file: str | None = None
) -> bool:
    if source.get("selection_required") is not True:
        return True

    try:
        result = subprocess.run(
            metadata_command(str(source["canonical_url"]), cookie_file=cookie_file),
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
    except subprocess.CalledProcessError as exc:
        _write_process_error("failed to inspect Bilibili parts", exc)
        return False
    except OSError as exc:
        _write_run_error(exc)
        return False

    try:
        metadata = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        sys.stderr.write(f"error: invalid metadata JSON: {exc}\n")
        return False
    if not isinstance(metadata, dict):
        sys.stderr.write("error: invalid metadata JSON: expected an object\n")
        return False
    try:
        validate_bilibili_part_selection(source, metadata)
    except ValueError as exc:
        sys.stderr.write(f"error: {exc}\n")
        return False
    return True


def _run_plan_frames(args: argparse.Namespace) -> None:
    timestamps = plan_candidate_timestamps(
        args.start_ms,
        args.end_ms,
        args.interval_ms,
    )
    print(json.dumps(timestamps, ensure_ascii=False))


def _run_verify_asset(args: argparse.Namespace) -> int:
    report = verify_asset(Path(args.asset))
    print(json.dumps(report, ensure_ascii=False))
    return 0 if report["valid"] else 1


def _run_validate_knowledge(args: argparse.Namespace) -> int:
    report = validate_asset_knowledge(Path(args.asset))
    print(json.dumps(report, ensure_ascii=False))
    return 0 if report["valid"] else 1


def _run_complete_stage(args: argparse.Namespace) -> int:
    """Record a stage and the current SHA-256 of each of its outputs.

    Stage manifests are part of the asset contract, so the agent must not
    hand-edit `manifest.json` or write a one-off script to hash outputs.
    """
    stage = args.stage
    if not _STAGE_NAME_PATTERN.match(stage):
        sys.stderr.write(
            f"error: unsupported stage name: {stage}; expected source, evidence, "
            "knowledge, content, views, views/<profile>, views/<profile>/plan, "
            "outputs, or outputs/<profile>\n"
        )
        return 1

    asset_root = Path(args.asset)
    try:
        store = AssetStore(root=asset_root)
        if args.schema_version is None:
            store.complete_stage(stage, args.outputs)
        else:
            store.complete_stage(stage, args.outputs, schema_version=args.schema_version)
        manifest = json.loads((asset_root / "manifest.json").read_text(encoding="utf-8"))
        record = manifest["stages"][stage]
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        sys.stderr.write(f"error: failed to complete stage {stage}: {exc}\n")
        return 1

    print(
        json.dumps(
            {"stage": stage, "completed_at": record["completed_at"], "outputs": record["outputs"]},
            ensure_ascii=False,
        )
    )
    return 0


def _run_cleanup_l2(args: argparse.Namespace) -> int:
    asset = Path(args.asset)
    plan = plan_l2_cleanup(asset)
    if args.apply:
        plan = execute_l2_cleanup(asset, plan)
    print(json.dumps(plan, ensure_ascii=False))
    return 0


def _run_build_qa_index(args: argparse.Namespace) -> int:
    manifest = build_qa_index(Path(args.asset), profile_id=args.profile)
    print(json.dumps(manifest, ensure_ascii=False))
    return 0


def _run_build_qa_topology(args: argparse.Namespace) -> int:
    topology = build_qa_topology(Path(args.asset), profile_id=args.profile)
    print(json.dumps(topology, ensure_ascii=False))
    return 0


def _run_retrieve_qa(args: argparse.Namespace) -> int:
    pack = retrieve_question(
        Path(args.asset),
        args.question,
        profile_id="course-notes",
        mode=args.mode,
        limit=args.limit,
    )
    if "answer" in pack:
        raise ValueError("retrieval pack must not include an answer")
    print(json.dumps(pack, ensure_ascii=False))
    return 0


def _run_plan_qa(args: argparse.Namespace) -> int:
    try:
        pack = json.loads(Path(args.input).read_text(encoding="utf-8"))
        if not isinstance(pack, Mapping):
            raise ValueError("grounding pack is not an object")
        if "answer" in pack or "claims" in pack:
            raise ValueError("grounding pack contains answer content")
        plan = build_answer_plan(pack)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError):
        sys.stderr.write("error: grounding pack failed validation\n")
        return 1
    if "answer" in plan or "claims" in plan:
        sys.stderr.write("error: grounding pack failed validation\n")
        return 1
    print(json.dumps(plan, ensure_ascii=False))
    return 0


def _run_validate_answer(args: argparse.Namespace) -> int:
    try:
        payload = json.loads(Path(args.input).read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        _write_answer_validation_errors(["answer input must be a valid JSON object"])
        return 1
    if not isinstance(payload, Mapping):
        _write_answer_validation_errors(["answer input must be a JSON object"])
        return 1

    try:
        answer = GroundedAnswer.model_validate(payload)
    except ValidationError as exc:
        _write_answer_validation_errors(_answer_contract_errors(exc))
        return 1

    errors = validate_grounded_answer(Path(args.asset), answer)
    if errors:
        _write_answer_validation_errors(errors)
        return 1
    print("answer passed validation")
    return 0


def _run_register_external_evidence(args: argparse.Namespace) -> int:
    path = register_external_evidence(Path(args.asset), Path(args.input))
    print(json.dumps({"external_evidence_path": str(path)}))
    return 0


def _run_validate_external_evidence(args: argparse.Namespace) -> int:
    _, errors = read_external_evidence(
        Path(args.asset) / EXTERNAL_EVIDENCE_PATH, required=True
    )
    if errors:
        _write_answer_validation_errors(errors)
        return 1
    print("external evidence passed validation")
    return 0


def _answer_contract_errors(exc: ValidationError) -> list[str]:
    """Render Pydantic validation messages without echoing submitted values."""
    return sorted(
        {
            f"answer contract error at {'.'.join(str(part) for part in item['loc'])}: {item['msg']}"
            for item in exc.errors()
        }
    )


def _write_answer_validation_errors(errors: Sequence[str]) -> None:
    sys.stderr.write("error: answer failed validation:\n")
    for error in errors:
        sys.stderr.write(f"- {error}\n")


def _run_select_profile(args: argparse.Namespace) -> int:
    selection = write_profile_selection(
        Path(args.asset),
        explicit_profile=args.profile,
        intent=args.intent,
        requested_formats=args.formats,
    )
    print(json.dumps(selection.model_dump(mode="json"), ensure_ascii=False))
    return 0


def _run_reproject_profile(args: argparse.Namespace) -> int:
    """Project one supplied authored document without a generation pathway."""
    try:
        document = json.loads(Path(args.document).read_text(encoding="utf-8"))
        if not isinstance(document, Mapping):
            raise ValueError("supplied authored document must be an object")
        output = reproject_profile_documents(
            Path(args.asset), {args.profile: document}
        )[args.profile]
    except (OSError, json.JSONDecodeError) as exc:
        sys.stderr.write(f"error: failed to read supplied authored document: {exc}\n")
        return 1
    except (ValueError, RuntimeError) as exc:
        sys.stderr.write(f"error: profile projection failed: {exc}\n")
        return 1
    print(json.dumps({"profile_id": args.profile, "document_path": str(output)}))
    return 0


def _run_validate_projection_plan(args: argparse.Namespace) -> int:
    try:
        plan = json.loads(Path(args.input).read_text(encoding="utf-8"))
        spec = get_profile(args.profile)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        sys.stderr.write(f"error: failed to read projection plan: {exc}\n")
        return 1
    errors = validate_projection_plan(
        plan, profile_id=args.profile, required_sections=spec.required_sections
    )
    if errors:
        sys.stderr.write(f"error: {args.profile} projection plan failed validation:\n")
        for error in errors:
            sys.stderr.write(f"- {error}\n")
        return 1
    print(f"{args.profile} projection plan passed validation")
    return 0


def _run_write_projection_plan(args: argparse.Namespace) -> int:
    try:
        plan = json.loads(Path(args.input).read_text(encoding="utf-8"))
        if not isinstance(plan, Mapping):
            raise ValueError("projection plan must be an object")
        path = write_projection_plan(
            Path(args.asset), profile_id=args.profile, plan=plan
        )
    except (OSError, json.JSONDecodeError, ValueError, RuntimeError) as exc:
        sys.stderr.write(f"error: projection plan write failed: {exc}\n")
        return 1
    print(json.dumps({"profile_id": args.profile, "projection_plan_path": str(path)}))
    return 0


def _run_render_course(args: argparse.Namespace) -> int:
    input_path = Path(args.input)
    output_path = Path(args.output)
    try:
        document = json.loads(input_path.read_text(encoding="utf-8"))
        if args.quality_floor == "p1":
            quality_errors = validate_course_document_quality(document)
            if quality_errors:
                sys.stderr.write("error: course document failed P1 quality gate:\n")
                for error in quality_errors:
                    sys.stderr.write(f"- {error}\n")
                return 1
        title, sections = _course_document_parts(document)
        tex = render_course_tex(
            title,
            sections,
            cover_image=_optional_string(document, "cover_image"),
            subtitle=_optional_string(document, "subtitle"),
            theme=_optional_string(document, "theme"),
            one_sentence_summary=_optional_string(document, "one_sentence_summary"),
            metadata=_optional_mapping(document, "metadata"),
        )
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(tex, encoding="utf-8")
    except json.JSONDecodeError as exc:
        sys.stderr.write(f"error: invalid course document JSON: {exc}\n")
        return 1
    except ValueError as exc:
        sys.stderr.write(f"error: invalid course document: {exc}\n")
        return 1
    except OSError as exc:
        sys.stderr.write(f"error: failed to render course: {exc}\n")
        return 1

    return 0


def _run_render_markdown(args: argparse.Namespace) -> int:
    input_path = Path(args.input)
    output_path = Path(args.output)
    try:
        document = json.loads(input_path.read_text(encoding="utf-8"))
        if args.quality_floor == "p1":
            quality_errors = validate_course_document_quality(document)
            if quality_errors:
                sys.stderr.write("error: course document failed P1 quality gate:\n")
                for error in quality_errors:
                    sys.stderr.write(f"- {error}\n")
                return 1
        title, sections = _course_document_parts(document)
        markdown = render_course_markdown(
            title,
            sections,
            cover_image=_optional_string(document, "cover_image"),
            subtitle=_optional_string(document, "subtitle"),
            theme=_optional_string(document, "theme"),
            one_sentence_summary=_optional_string(document, "one_sentence_summary"),
            metadata=_optional_mapping(document, "metadata"),
        )
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(markdown, encoding="utf-8")
    except json.JSONDecodeError as exc:
        sys.stderr.write(f"error: invalid course document JSON: {exc}\n")
        return 1
    except ValueError as exc:
        sys.stderr.write(f"error: invalid course document: {exc}\n")
        return 1
    except OSError as exc:
        sys.stderr.write(f"error: failed to render markdown: {exc}\n")
        return 1

    return 0


def _run_render_html(args: argparse.Namespace) -> int:
    input_path = Path(args.input)
    output_path = Path(args.output)
    try:
        document = json.loads(input_path.read_text(encoding="utf-8"))
        if args.quality_floor == "p1":
            quality_errors = validate_course_document_quality(document)
            if quality_errors:
                sys.stderr.write("error: course document failed P1 quality gate:\n")
                for error in quality_errors:
                    sys.stderr.write(f"- {error}\n")
                return 1
        title, sections = _course_document_parts(document)
        html = render_course_html(
            title,
            sections,
            cover_image=_optional_string(document, "cover_image"),
            subtitle=_optional_string(document, "subtitle"),
            theme=_optional_string(document, "theme"),
            one_sentence_summary=_optional_string(document, "one_sentence_summary"),
            metadata=_optional_mapping(document, "metadata"),
        )
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(html, encoding="utf-8")
    except json.JSONDecodeError as exc:
        sys.stderr.write(f"error: invalid course document JSON: {exc}\n")
        return 1
    except ValueError as exc:
        sys.stderr.write(f"error: invalid course document: {exc}\n")
        return 1
    except OSError as exc:
        sys.stderr.write(f"error: failed to render html: {exc}\n")
        return 1

    return 0


def _run_validate_document(args: argparse.Namespace) -> int:
    try:
        document = json.loads(Path(args.input).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        sys.stderr.write(f"error: failed to read course document: {exc}\n")
        return 1

    errors = validate_document_quality(document, profile_id=args.profile)
    errors.extend(validate_document_image_files(document, _document_asset_root(Path(args.input))))
    if errors:
        sys.stderr.write(f"error: {args.profile} document failed quality gate:\n")
        for error in errors:
            sys.stderr.write(f"- {error}\n")
        return 1

    print(f"{args.profile} document passed quality gate")
    return 0


def _run_render_document(args: argparse.Namespace) -> int:
    input_path = Path(args.input)
    output_path = Path(args.output)
    try:
        document = json.loads(input_path.read_text(encoding="utf-8"))
        if not isinstance(document, Mapping):
            raise ValueError("document must be an object")
        declared_profile = document.get("profile_id")
        if declared_profile != args.profile:
            raise ValueError("document profile_id must match --profile")
        errors = validate_document_quality(document, profile_id=args.profile)
        errors.extend(validate_document_image_files(document, _document_asset_root(input_path)))
        if errors:
            sys.stderr.write(f"error: {args.profile} document failed quality gate:\n")
            for error in errors:
                sys.stderr.write(f"- {error}\n")
            return 1
        rendered = _render_document_format(
            document,
            args.format,
            asset_root=_document_asset_root(input_path),
            output_directory=output_path.parent,
        )
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(rendered, encoding="utf-8")
    except json.JSONDecodeError as exc:
        sys.stderr.write(f"error: invalid document JSON: {exc}\n")
        return 1
    except ValueError as exc:
        sys.stderr.write(f"error: invalid document: {exc}\n")
        return 1
    except OSError as exc:
        sys.stderr.write(f"error: failed to render document: {exc}\n")
        return 1
    return 0


def render_all_formats(
    document: object,
    output_directory: str | Path,
    *,
    asset_root: str | Path | None = None,
) -> dict[str, Path]:
    """Write the three source formats from exactly one renderer-neutral document."""
    if asset_root is not None:
        image_errors = validate_document_image_files(document, asset_root)
        if image_errors:
            raise ValueError("; ".join(image_errors))
    directory = Path(output_directory)
    directory.mkdir(parents=True, exist_ok=True)
    outputs = {
        "md": directory / "document.md",
        "html": directory / "document.html",
        "tex": directory / "document.tex",
    }
    for format_name, output_path in outputs.items():
        output_path.write_text(
            _render_document_format(
                document,
                format_name,
                asset_root=asset_root,
                output_directory=output_path.parent if asset_root is not None else None,
            ),
            encoding="utf-8",
        )
    return outputs


def _render_document_format(
    document: Mapping[str, object],
    format_name: str,
    *,
    asset_root: str | Path | None = None,
    output_directory: str | Path | None = None,
) -> str:
    if format_name == "md":
        return render_document_markdown(
            document,
            asset_root=str(asset_root) if asset_root is not None else None,
            output_directory=str(output_directory) if output_directory is not None else None,
        )
    if format_name == "html":
        return render_document_html(
            document,
            asset_root=str(asset_root) if asset_root is not None else None,
            output_directory=str(output_directory) if output_directory is not None else None,
        )
    if format_name == "tex":
        return render_document_tex(
            document,
            asset_root=str(asset_root) if asset_root is not None else None,
            output_directory=str(output_directory) if output_directory is not None else None,
        )
    raise ValueError("document format must be md, html, or tex")


def _document_asset_root(document_path: Path) -> Path:
    """Resolve views/<profile>/document.json paths back to their asset root."""
    parent = document_path.parent
    if parent.parent.name == "views":
        return parent.parent.parent
    return parent


def _run_validate_teaching_outline(args: argparse.Namespace) -> int:
    try:
        outline = json.loads(Path(args.input).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        sys.stderr.write(f"error: failed to read teaching outline: {exc}\n")
        return 1

    errors = validate_teaching_outline(outline)
    if errors:
        sys.stderr.write("error: teaching outline failed quality gate:\n")
        for error in errors:
            sys.stderr.write(f"- {error}\n")
        return 1

    print("teaching outline passed quality gate")
    return 0


def _run_compile_pdf(args: argparse.Namespace) -> int:
    xelatex = find_command("xelatex")
    if xelatex is None:
        sys.stderr.write(
            "error: xelatex was not found on PATH; "
            "install TeX Live or MiKTeX to compile PDFs\n"
        )
        return 1

    tex_path = Path(args.tex)
    output_directory = Path(args.output_directory)
    output_directory.mkdir(parents=True, exist_ok=True)
    command = [
        str(xelatex),
        "-interaction=nonstopmode",
        "-halt-on-error",
        "-output-directory",
        str(output_directory),
        str(tex_path),
    ]

    try:
        for _ in range(2):
            subprocess.run(
                command,
                check=True,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
    except subprocess.CalledProcessError as exc:
        log_path = _latex_log_path(output_directory)
        _write_latex_build_log(log_path, exc.stdout, exc.stderr)
        sys.stderr.write(
            f"error: xelatex failed (exit {exc.returncode}); see {log_path}\n"
        )
        return exc.returncode or 1
    except OSError as exc:
        sys.stderr.write(f"error: failed to run xelatex: {exc}\n")
        return 1

    return 0


def _course_document_parts(document: object) -> tuple[str, Sequence[object]]:
    if isinstance(document, Mapping):
        title = document.get("title", "课程笔记")
        if not isinstance(title, str):
            raise ValueError("course document title must be a string")
        if "sections" not in document:
            raise ValueError("course document sections must be present")
        sections = document["sections"]
    elif isinstance(document, Sequence) and not isinstance(document, (str, bytes)):
        title = "课程笔记"
        sections = document
    else:
        raise ValueError(
            "course document must be an object with sections or a sections array"
        )

    if not isinstance(sections, list):
        raise ValueError("course document sections must be a list")

    return title, sections


def _optional_string(document: object, key: str) -> str | None:
    if not isinstance(document, Mapping):
        return None
    value = document.get(key)
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError(f"course document {key} must be a string")
    return value or None


def _optional_mapping(document: object, key: str) -> Mapping[str, object] | None:
    if not isinstance(document, Mapping):
        return None
    value = document.get(key)
    if value is None:
        return None
    if not isinstance(value, Mapping):
        raise ValueError(f"course document {key} must be an object")
    return value


def _latex_log_path(output_directory: Path) -> Path:
    log_directory = output_directory.parent / "logs"
    try:
        log_directory.mkdir(parents=True, exist_ok=True)
    except OSError:
        return output_directory / "latex-build.log"
    return log_directory / "latex-build.log"


def _write_latex_build_log(
    log_path: Path,
    stdout: str | None,
    stderr: str | None,
) -> None:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text(
        "\n".join(
            [
                "STDOUT:",
                stdout or "",
                "",
                "STDERR:",
                stderr or "",
            ]
        ),
        encoding="utf-8",
    )


def _write_process_error(message: str, exc: subprocess.CalledProcessError) -> None:
    sys.stderr.write(f"error: {message} with yt-dlp (exit {exc.returncode})\n")


def _write_run_error(exc: OSError) -> None:
    sys.stderr.write("error: failed to run yt-dlp\n")


def _validated_cookie_file(value: str | None) -> str | None:
    if value is None:
        return None
    try:
        is_file = Path(value).is_file()
    except OSError:
        is_file = False
    if not is_file:
        raise ValueError("cookie file must be a regular file")
    return value


def _srt_files(directory: Path) -> set[Path]:
    if not directory.exists():
        return set()
    return {path.resolve() for path in directory.glob("*.srt") if path.is_file()}


def _read_jsonl(path: Path) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        row = json.loads(line)
        if not isinstance(row, dict):
            raise ValueError(f"{path}:{line_number} must contain a JSON object")
        rows.append(row)
    return rows


def _read_json_object(path: Path, label: str) -> dict[str, object]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{label} must be a JSON object")
    return payload


if __name__ == "__main__":
    raise SystemExit(main())
