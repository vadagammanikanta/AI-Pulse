"""Tests for hallucination validator on learning modules."""
from __future__ import annotations

import pytest
from app.ai.validator import sanitize_item_output
from app.schemas.item import ItemAIOutput, PaperLearningModule, TutorialLearningModule


# ---------------------------------------------------------------------------
# Helper factories
# ---------------------------------------------------------------------------

def _paper_output(**lm_kwargs) -> ItemAIOutput:
    return ItemAIOutput(
        what_is_new="The authors propose a new methodology.",
        why_it_matters="Improves accuracy according to researchers.",
        who_should_care=["developers"],
        how_to_use="Read the paper carefully.",
        pro_tip="Focus on the evaluation section.",
        category="paper",
        importance_score=70,
        importance_reason="Novel approach",
        learning_module=PaperLearningModule(**lm_kwargs) if lm_kwargs else None,
    )


def _tool_output(**lm_kwargs) -> ItemAIOutput:
    return ItemAIOutput(
        what_is_new="A new tool was released.",
        why_it_matters="Speeds up workflows.",
        who_should_care=["developers"],
        how_to_use="Use the tool as described.",
        pro_tip="Check the changelog.",
        category="tool",
        importance_score=80,
        importance_reason="Useful tool",
        learning_module=TutorialLearningModule(**lm_kwargs) if lm_kwargs else None,
    )


# ---------------------------------------------------------------------------
# Group 1: install / URL patterns (original tests, updated for new API)
# ---------------------------------------------------------------------------

def test_flags_hallucinated_pip_install():
    output = _tool_output(
        tutorial_5min="1. Run pip install fake-hallucinated-package-xyz to install.",
        skill_gained="Installation",
    )
    result, vr = sanitize_item_output(output, "A Novel Tool", "We present a tool on AI methods.")
    assert result.learning_module is None
    assert vr == "nulled"


def test_allows_valid_tool_in_source():
    output = _tool_output(
        tutorial_5min="1. Run pip install vllm to install.",
        skill_gained="vLLM deployment",
    )
    result, vr = sanitize_item_output(
        output,
        "vLLM 0.6 Released",
        "Install vllm using pip install vllm for fast LLM inference.",
    )
    assert result.learning_module is not None
    assert vr == "passed"


def test_flags_git_clone_hallucination():
    output = _tool_output(
        tutorial_5min="Clone the phantom-repo repo to get started.",
        skill_gained="Cloning",
    )
    result, vr = sanitize_item_output(output, "Some Tool", "No repo is mentioned here.")
    assert result.learning_module is None
    assert vr == "nulled"


def test_flags_url_not_in_source():
    output = _tool_output(
        tutorial_5min="Visit https://invented.example.com/docs to get started.",
        skill_gained="API use",
    )
    result, vr = sanitize_item_output(output, "New API", "No URL was provided.")
    assert result.learning_module is None
    assert vr == "nulled"


# ---------------------------------------------------------------------------
# Group 2: structural artifact patterns (new tests)
# Three REAL failing lessons from the previous session as fixtures.
# ---------------------------------------------------------------------------

def test_breaking_babel_appendix_reference():
    """Lesson mentions 'Getting Started code snippet in the appendix' — invented."""
    output = _paper_output(
        key_idea="The authors propose Breaking Babel for multilingual AI.",
        read_for="Evaluate the multilingual transfer method.",
        skill_gained="Multilingual NLP understanding",
        next_topic="Cross-lingual transfer",
    )
    # Inject the bad text manually into key_idea to simulate the hallucinated lesson
    output.learning_module.key_idea = (
        "The authors claim new SOTA. Getting Started code snippet in the appendix "
        "shows how to use the provided SMART demo."
    )
    result, vr = sanitize_item_output(
        output,
        "Breaking Babel: Evaluating Multilingual AI",
        "We present a new multilingual benchmark. The authors claim significant improvements.",
    )
    assert result.learning_module is None
    assert vr == "nulled"


def test_dattri_readme_and_filename():
    """Lesson mentions README and example_attribution.py — both invented."""
    output = _paper_output(
        key_idea="dattri enables training data attribution for LLMs.",
        read_for="Focus on the attribution algorithm.",
        skill_gained="Training data attribution",
        next_topic="Data valuation methods",
    )
    output.learning_module.read_for = (
        "See the Getting Started code snippet in the README and run example_attribution.py."
    )
    result, vr = sanitize_item_output(
        output,
        "dattri: Training Data Attribution for LLMs",
        "We introduce dattri, a library for training data attribution.",
    )
    assert result.learning_module is None
    assert vr == "nulled"


def test_computersd_provided_example_script():
    """Lesson mentions 'provided example script' — invented."""
    output = _paper_output(
        key_idea="ComputerSD automates computer use via screen diffusion.",
        read_for="Evaluate the screen parsing method.",
        skill_gained="Computer use automation understanding",
        next_topic="Multimodal agents",
    )
    output.learning_module.read_for = (
        "Run the provided example script to see the model in action."
    )
    result, vr = sanitize_item_output(
        output,
        "ComputerSD: Screen Diffusion for Computer Use",
        "We propose ComputerSD for automated computer use via diffusion.",
    )
    assert result.learning_module is None
    assert vr == "nulled"


def test_section_number_not_in_source():
    """Lesson mentions 'Section 3' but source has no section numbers."""
    output = _paper_output(
        key_idea="The authors introduce a new attention mechanism.",
        read_for="Focus on Section 3 which describes the architecture.",
        skill_gained="Attention mechanism understanding",
    )
    result, vr = sanitize_item_output(
        output,
        "Efficient Attention for Long Sequences",
        "We propose a linear attention mechanism for transformers.",
    )
    assert result.learning_module is None
    assert vr == "nulled"


def test_filename_not_in_source():
    """Lesson mentions train.py — not in source."""
    output = _paper_output(
        key_idea="The authors release a training framework.",
        read_for="Check the experimental setup and then run train.py.",
        skill_gained="Framework understanding",
    )
    result, vr = sanitize_item_output(
        output,
        "Fast Training Framework",
        "We present a framework for efficient model training.",
    )
    assert result.learning_module is None
    assert vr == "nulled"


def test_demo_word_not_in_source():
    """Lesson mentions 'demo' but source doesn't."""
    output = _tool_output(
        tutorial_5min="Try the live demo to explore the model capabilities.",
        skill_gained="Model exploration",
    )
    result, vr = sanitize_item_output(
        output,
        "New Language Model Released",
        "The team releases a new language model for text generation.",
    )
    assert result.learning_module is None
    assert vr == "nulled"


def test_demo_word_allowed_when_in_source():
    """'demo' is allowed if the source mentions it."""
    output = _tool_output(
        tutorial_5min="Try the interactive demo to see the model in action.",
        skill_gained="Model demonstration",
    )
    result, vr = sanitize_item_output(
        output,
        "Model with Live Demo Released",
        "The team provides an interactive demo for users to explore.",
    )
    assert result.learning_module is not None
    assert vr == "passed"


# ---------------------------------------------------------------------------
# No learning_module → skipped
# ---------------------------------------------------------------------------

def test_no_learning_module_returns_skipped():
    output = _tool_output()  # no lm_kwargs → learning_module=None
    result, vr = sanitize_item_output(output, "Some Title", "Some excerpt.")
    assert result.learning_module is None
    assert vr == "skipped"


# ---------------------------------------------------------------------------
# Paper module with clean content → passed
# ---------------------------------------------------------------------------

def test_clean_paper_module_passes():
    output = _paper_output(
        key_idea="The authors introduce sparse attention for long contexts.",
        read_for="Focus on the evaluation on long-document benchmarks.",
        prerequisite_concepts=["transformer architecture", "attention mechanisms"],
        skill_gained="Sparse attention comprehension",
        next_topic="Long-context language models",
    )
    result, vr = sanitize_item_output(
        output,
        "Sparse Attention for Long-Document Understanding",
        "We propose a sparse attention method that scales linearly with sequence length.",
    )
    assert result.learning_module is not None
    assert vr == "passed"
