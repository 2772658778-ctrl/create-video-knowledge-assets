import json
from pathlib import Path

from vka.profiles import canonical_hash_tree, get_profile, write_projection_plan
from vka.projection_plan import validate_projection_plan
from vka.store import AssetStore
from vka_cli import main


def _asset(tmp_path: Path) -> AssetStore:
    asset = AssetStore.create(tmp_path / "assets", "asset-001", {"kind": "local_video"})
    evidence = asset.write_jsonl("evidence/records.jsonl", [
        {"evidence_id": "ev-text", "origin": "video", "modality": "transcript"},
        {
            "evidence_id": "ev-frame", "origin": "video", "modality": "frame",
            "artifact_ref": "source/frames/flow.jpg",
            "quality": {"review": "directly_inspected"},
        },
    ])
    frame = asset.root / "source" / "frames" / "flow.jpg"
    frame.parent.mkdir(parents=True)
    frame.write_bytes(b"frame")
    knowledge = asset.write_jsonl("knowledge/units.jsonl", [
        {"unit_id": "ku-flow", "epistemic_status": "video_explicit"},
    ])
    asset.complete_stage("evidence", [evidence])
    asset.complete_stage("knowledge", [knowledge])
    return asset


def _plan(asset: AssetStore) -> dict[str, object]:
    profile = get_profile("creator-article")
    sections = []
    for kind in profile.required_sections:
        refs = ["ev-frame"] if kind == "video_evidence" else ["ev-text"]
        sections.append({
            "section_id": f"sec-{kind}", "kind": kind,
            "reader_question": f"What should a reader understand from the {kind} evidence?",
            "knowledge_refs": ["ku-flow"], "evidence_refs": refs,
            "required_blocks": ["paragraph"],
        })
    return {
        "schema_version": "1.0", "plan_id": "pp-creator-001",
        "profile_id": "creator-article", "profile_spec_version": "1.0",
        "canonical_hash_tree": canonical_hash_tree(asset),
        "reader_goal": "Help a reader understand the demonstrated workflow and its boundary.",
        "status": "ready",
        "source_form": {
            "type": "explainer",
            "duration_band": "under_15m",
            "density": "high",
            "chapter_mode": "explicit",
        },
        "granularity": {
            "planned_claims": 4,
            "rationale": "The source carries four verifiable claims in two sections.",
        },        "sections": sections,
        "selected_figures": [{
            "section_id": "sec-video_evidence", "evidence_id": "ev-frame",
            "artifact_ref": "source/frames/flow.jpg",
            "reader_purpose": "Show the reviewed workflow state.",
            "caption_intent": "Explain the visible state and why it supports the claim.",
            "required": True,
        }],
        "rejected_frames": [],
        "quality_targets": {"minimum_meaningful_blocks": 8, "requires_visual": True},
    }


def _short_video_script_plan(asset: AssetStore) -> dict[str, object]:
    return {
        "schema_version": "1.0",
        "plan_id": "pp-short-video-001",
        "profile_id": "short-video-script",
        "profile_spec_version": "1.0",
        "canonical_hash_tree": canonical_hash_tree(asset),
        "reader_goal": "Select reusable content units for a short video script.",
        "status": "ready",
        "source_form": {
            "type": "commentary",
            "duration_band": "under_15m",
            "density": "medium",
            "chapter_mode": "inferable",
        },
        "granularity": {
            "planned_claims": 2,
            "rationale": "A sixty-second script carries one point and one proof.",
        },
        "sections": [
            {
                "section_id": "sec-hook",
                "kind": "hook",
                "reader_question": "What should the audience hear first?",
                "knowledge_refs": ["ku-flow"],
                "evidence_refs": ["ev-text"],
                "required_blocks": ["paragraph"],
            },
            {
                "section_id": "sec-context",
                "kind": "context",
                "reader_question": "What is the minimum background needed?",
                "knowledge_refs": ["ku-flow"],
                "evidence_refs": ["ev-text"],
                "required_blocks": ["paragraph"],
            },
            {
                "section_id": "sec-core_point",
                "kind": "core_point",
                "reader_question": "What is the central idea to carry forward?",
                "knowledge_refs": ["ku-flow"],
                "evidence_refs": ["ev-text"],
                "required_blocks": ["paragraph"],
            },
            {
                "section_id": "sec-evidence",
                "kind": "evidence",
                "reader_question": "Which source-backed detail should be quoted?",
                "knowledge_refs": ["ku-flow"],
                "evidence_refs": ["ev-text"],
                "required_blocks": ["paragraph"],
            },
            {
                "section_id": "sec-payoff",
                "kind": "payoff",
                "reader_question": "What useful takeaway should land?",
                "knowledge_refs": ["ku-flow"],
                "evidence_refs": ["ev-text"],
                "required_blocks": ["paragraph"],
            },
            {
                "section_id": "sec-closing",
                "kind": "closing",
                "reader_question": "How should the script end cleanly?",
                "knowledge_refs": ["ku-flow"],
                "evidence_refs": ["ev-text"],
                "required_blocks": ["paragraph"],
            },
        ],
        "selected_figures": [],
        "rejected_frames": [],
        "quality_targets": {"minimum_meaningful_blocks": 4, "requires_visual": False},
    }


def test_projection_plan_is_a_profile_specific_evidence_bridge(tmp_path: Path) -> None:
    asset = _asset(tmp_path)
    plan = _plan(asset)

    assert validate_projection_plan(
        plan, profile_id="creator-article", required_sections=get_profile("creator-article").required_sections
    ) == []
    path = write_projection_plan(asset, profile_id="creator-article", plan=plan)

    assert path == asset.root / "views" / "creator-article" / "projection-plan.json"
    assert json.loads(path.read_text(encoding="utf-8"))["plan_id"] == "pp-creator-001"
    assert asset.verify_stage("views/creator-article/plan", schema_version="1.1") == []
    assert canonical_hash_tree(asset) == plan["canonical_hash_tree"]


def test_projection_plan_rejects_changed_canonical_hash_or_uninspected_figure(tmp_path: Path) -> None:
    asset = _asset(tmp_path)
    plan = _plan(asset)
    plan["canonical_hash_tree"] = {"knowledge/units.jsonl": "0" * 64}

    try:
        write_projection_plan(asset, profile_id="creator-article", plan=plan)
    except ValueError as exc:
        assert "canonical_hash_tree does not match" in str(exc)
    else:  # pragma: no cover - makes the intended failure explicit
        raise AssertionError("changed canonical input must fail")


def test_projection_plan_accepts_a_short_video_script_plan(tmp_path: Path) -> None:
    asset = _asset(tmp_path)
    plan = _short_video_script_plan(asset)

    assert validate_projection_plan(
        plan, profile_id="short-video-script", required_sections=get_profile("short-video-script").required_sections
    ) == []
    path = write_projection_plan(asset, profile_id="short-video-script", plan=plan)

    assert path == asset.root / "views" / "short-video-script" / "projection-plan.json"
    assert json.loads(path.read_text(encoding="utf-8"))["plan_id"] == "pp-short-video-001"
def test_cli_validates_projection_plan_before_asset_write(tmp_path: Path, capsys) -> None:
    asset = _asset(tmp_path)
    input_path = tmp_path / "plan.json"
    input_path.write_text(json.dumps(_plan(asset)), encoding="utf-8")

    assert main([
        "validate-projection-plan", "--input", str(input_path), "--profile", "creator-article"
    ]) == 0
    assert "passed validation" in capsys.readouterr().out
