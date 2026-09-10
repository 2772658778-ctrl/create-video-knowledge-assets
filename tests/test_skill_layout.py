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


def test_p4_qa_is_not_part_of_the_main_skill_workflow() -> None:
    skill_text = (SKILL / "SKILL.md").read_text(encoding="utf-8")
    main_text = skill_text.split("## References", maxsplit=1)[0]

    for required in ("Q&A is not part of the main product boundary", "future skill"):
        assert required in skill_text
    for prohibited in (
        "## Grounded Q&A",
        "p4-qa.md",
        "p4-video-topology.md",
        "p4-qa-authoring.md",
        "p4-qa-evaluation.md",
        "p4-external-evidence.md",
        "p4-answer-presentation.md",
        "build-qa-index",
        "build-qa-topology",
        "retrieve-qa",
        "plan-qa",
        "validate-answer",
        "GroundedAnswer",
    ):
        assert prohibited not in main_text
