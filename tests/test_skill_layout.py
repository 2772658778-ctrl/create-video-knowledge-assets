from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "create-video-knowledge-assets"


def test_skill_has_required_resources() -> None:
    assert (SKILL / "SKILL.md").is_file()
    assert (SKILL / "agents" / "openai.yaml").is_file()
    assert (SKILL / "scripts").is_dir()
    assert (SKILL / "references").is_dir()
    assert (SKILL / "assets").is_dir()


def test_final_skill_does_not_bundle_a_baseline_copy() -> None:
    assert not (SKILL / "baselines").exists()


def test_default_prompt_names_p1_input_and_skill() -> None:
    metadata = yaml.safe_load((SKILL / "agents" / "openai.yaml").read_text(encoding="utf-8"))
    prompt = metadata["interface"]["default_prompt"]
    assert "$create-video-knowledge-assets" in prompt
    assert "Bilibili" in prompt


def test_acquisition_recipes_keep_direct_tools_inside_asset_boundaries() -> None:
    skill_text = (SKILL / "SKILL.md").read_text(encoding="utf-8")
    recipes = (SKILL / "references" / "acquisition-recipes.md").read_text(
        encoding="utf-8"
    )

    assert "references/acquisition-recipes.md" in skill_text
    for required in (
        "yt-dlp",
        "ffmpeg",
        "ffprobe",
        "whisper",
        "source/",
        "evidence/",
        "timeline.raw.jsonl",
        "timeline.jsonl",
        "directly_inspected",
        "cleanup-l2 --dry-run",
    ):
        assert required in recipes
    assert "--cookies-from-browser" in recipes
    assert "Do not use `--cookies-from-browser`" in recipes


def test_p2_navigation_and_sanitized_u1_acceptance_materials() -> None:
    skill_text = (SKILL / "SKILL.md").read_text(encoding="utf-8")
    prompt = yaml.safe_load(
        (SKILL / "agents" / "openai.yaml").read_text(encoding="utf-8")
    )["interface"]["default_prompt"]
    workflow = (SKILL / "references" / "p2-u1-workflow.md").read_text(encoding="utf-8")
    workflow_lower = workflow.lower()
    acceptance = (ROOT / "tests" / "fixtures" / "p2-u1-acceptance.md").read_text(
        encoding="utf-8"
    )

    for required in (
        "local video",
        "general-deep",
        "profile-course-notes.md",
        "p2-u1-workflow.md",
        "p1-workflow.md",
        "validate-teaching-outline",
    ):
        assert required in skill_text
    assert "local video" in prompt
    assert "Bilibili" in prompt
    assert "general-deep" in prompt

    for required in (
        "input",
        "recovery",
        "l2",
        "general-deep",
        "profile-general-deep.md",
        "profile-course-notes.md",
        "stop",
        "degrade",
        "outputs",
        "human review",
    ):
        assert required in workflow_lower

    for required in (
        "public URL",
        "input kind",
        "tool versions",
        "anonymized time",
        "stage hash",
        "format result",
        "human rubric",
        "L2 dryrun",
    ):
        assert required in acceptance
    for prohibited in ("Cookie", "cookie", "transcript", "media file"):
        assert prohibited not in acceptance
    assert "anonymous time" not in acceptance
    for extra_field in ("selected profile:", "reviewer decision:", "review notes:"):
        assert extra_field not in acceptance


def test_p3_profile_projection_navigation_and_acceptance_template() -> None:
    skill_text = (SKILL / "SKILL.md").read_text(encoding="utf-8")
    prompt = yaml.safe_load(
        (SKILL / "agents" / "openai.yaml").read_text(encoding="utf-8")
    )["interface"]["default_prompt"]
    workflow = (SKILL / "references" / "p3-profile-workflow.md").read_text(encoding="utf-8")
    acceptance = (ROOT / "tests" / "fixtures" / "p3-profile-acceptance.md").read_text(
        encoding="utf-8"
    )

    for required in (
        "profile-routing.md",
        "p3-profile-workflow.md",
        "p3-profile-authoring.md",
        "projection-plan.md",
        "verify-asset",
        "views/<profile_id>",
        "outputs/<profile_id>",
        "document-schema.md",
    ):
        assert required in skill_text
    assert "profile" in prompt.lower()
    for required in (
        "verify-asset",
        "canonical_hash_tree",
        "reproject_profile_documents",
        "source/",
        "evidence/",
        "knowledge/",
        "views/<profile_id>",
        "outputs/<profile_id>",
        "supplied authored document",
        "p3-profile-authoring.md",
    ):
        assert required in workflow
    for required in (
        "asset fingerprint",
        "route reason",
        "profile",
        "pre-projection canonical hashes",
        "post-projection canonical hashes",
        "format paths",
        "automatic gates",
        "PDF page inspection",
        "human comprehension score",
    ):
        assert required in acceptance


def test_p4_qa_navigation_is_limited_to_completed_course_notes_assets() -> None:
    skill_text = (SKILL / "SKILL.md").read_text(encoding="utf-8")
    workflow = (SKILL / "references" / "p4-qa.md").read_text(encoding="utf-8")
    topology = (SKILL / "references" / "p4-video-topology.md").read_text(encoding="utf-8")
    authoring = (SKILL / "references" / "p4-qa-authoring.md").read_text(encoding="utf-8")
    evaluation = (SKILL / "references" / "p4-qa-evaluation.md").read_text(encoding="utf-8")

    for required in (
        "completed course-notes asset",
        "p4-qa.md",
        "p4-video-topology.md",
        "p4-qa-authoring.md",
        "p4-qa-evaluation.md",
        "verify-asset",
        "build-qa-index",
        "build-qa-topology",
        "plan-qa",
        "retrieve-qa",
        "validate-answer",
    ):
        assert required in skill_text
    for required in (
        "verify-asset",
        "build-qa-index",
        "build-qa-topology",
        "retrieve-qa",
        "plan-qa",
        "GroundedAnswer",
        "v1.1",
        "without an answer_plan is invalid",
        "extensions",
        "out_of_scope",
        "insufficient_evidence",
    ):
        assert required in workflow
    command_order = (
        "verify-asset",
        "build-qa-index",
        "build-qa-topology",
        "retrieve-qa",
        "plan-qa",
        "GroundedAnswer",
        "validate-answer",
    )
    assert [workflow.index(command) for command in command_order] == sorted(
        workflow.index(command) for command in command_order
    )
    qa_section = skill_text.split("## Grounded Q&A", maxsplit=1)[1].split(
        "## References", maxsplit=1
    )[0]
    skill_command_order = (
        "verify-asset",
        "build-qa-index",
        "build-qa-topology",
        "retrieve-qa",
        "plan-qa",
        "author from the selected references",
        "validate-answer",
    )
    assert [qa_section.index(command) for command in skill_command_order] == sorted(
        qa_section.index(command) for command in skill_command_order
    )
    for required in ("facets", "capabilities", "build-qa-topology"):
        assert required in topology
    for required in ("retrieve", "plan", "selected", "evidence_windows", "blocks"):
        assert required in authoring
    for required in ("coverage", "readability", "limits"):
        assert required in evaluation
