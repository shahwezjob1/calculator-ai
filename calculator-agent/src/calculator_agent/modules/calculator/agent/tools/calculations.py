from typing import Annotated, Any

from langchain_core.messages import ToolMessage
from langchain_core.tools import InjectedToolCallId, tool
from langgraph.prebuilt import InjectedState
from langgraph.types import Command, interrupt

from calculator_agent.core.clients.calculations_api_client import CalculationsApiClient
from calculator_agent.core.clients.errors import UpstreamServiceError
from calculator_agent.core.clients.reviewer_api_client import ReviewerApiClient


ORIGIN_NEW = "new"
ORIGIN_EDIT = "edit"
SAVE_CALCULATION_INTERRUPT_TYPE = "save_calculation"


def _params_text(params: list[dict]) -> str:
    return "\n".join(f"- {p['name']}: {p['description']}" for p in params) or "- (none)"


def _format_draft(draft: dict) -> str:
    review = draft.get("review") or {}
    issues = "\n".join(
        f"- [{issue.get('type', '?')}] {issue.get('message', '')}"
        for issue in review.get("issues", [])
    ) or "- (none)"
    origin = f"editing '{draft['original_name']}'" if draft["origin"] == ORIGIN_EDIT else "new"

    return (
        f"Draft calculation ({origin}):\n"
        f"Name: {draft['name']}\n"
        f"Description: {draft['description']}\n"
        f"Params:\n{_params_text(draft['params'])}\n"
        f"Script:\n{draft['script']}\n"
        f"Review verdict: {review.get('verdict', '(not reviewed since manual edit)')}\n"
        f"Review issues:\n{issues}\n\n"
    )


def _draft_command(draft: dict | None, message: str, tool_call_id: str) -> Command:
    return Command(update={
        "calculation_draft": draft,
        "messages": [ToolMessage(content=message, tool_call_id=tool_call_id)],
    })


def _save_arguments_from_draft(draft: dict) -> dict[str, Any]:
    return {
        "operation": "update" if draft["origin"] == ORIGIN_EDIT else "create",
        "original_name": draft.get("original_name"),
        "name": draft["name"],
        "description": draft["description"],
        "params": draft["params"],
        "script": draft["script"],
    }


def _build_save_interrupt_payload(draft: dict) -> dict[str, Any]:
    return {
        "type": SAVE_CALCULATION_INTERRUPT_TYPE,
        "action_requests": [{
            "name": "save_calculation",
            "args": _save_arguments_from_draft(draft),
            "description": "Review the complete calculation before it is created or updated.",
        }],
        "review_configs": [{
            "allowed_decisions": ["approve", "edit", "reject"],
        }],
    }


def _extract_save_decision(
    resume_value: Any,
) -> tuple[str, dict[str, Any] | None, str | None]:
    if not isinstance(resume_value, dict):
        raise ValueError("Invalid save-calculation resume value")

    decisions = resume_value.get("decisions")
    if not isinstance(decisions, list) or len(decisions) != 1:
        raise ValueError("Exactly one decision is required for save_calculation")

    decision = decisions[0]
    if not isinstance(decision, dict):
        raise ValueError("Invalid save-calculation decision")

    decision_type = decision.get("type")
    if decision_type not in {"approve", "edit", "reject"}:
        raise ValueError(f"Unsupported save-calculation decision: {decision_type}")

    feedback = decision.get("message")
    if feedback is not None and not isinstance(feedback, str):
        raise ValueError("Decision message must be a string")

    if decision_type != "edit":
        return decision_type, None, feedback

    edited_action = decision.get("edited_action")
    if not isinstance(edited_action, dict):
        raise ValueError("edited_action is required for an edit decision")
    if edited_action.get("name") != "save_calculation":
        raise ValueError("The edited action must target save_calculation")

    edited_args = edited_action.get("args")
    if not isinstance(edited_args, dict):
        raise ValueError("Complete edited calculation arguments are required")

    return decision_type, edited_args, feedback


def _draft_from_save_arguments(current_draft: dict, args: dict[str, Any]) -> dict:
    required_fields = {"operation", "name", "description", "params", "script"}
    missing = sorted(required_fields - args.keys())
    if missing:
        raise ValueError(
            "Edited save arguments are missing required fields: " + ", ".join(missing)
        )

    operation = args["operation"]
    if operation not in {"create", "update"}:
        raise ValueError("operation must be either 'create' or 'update'")

    original_name = args.get("original_name")
    if operation == "update":
        if not isinstance(original_name, str) or not original_name:
            raise ValueError("original_name is required for an update operation")
    else:
        original_name = None

    edited_draft = dict(current_draft)
    edited_draft.update({
        "origin": ORIGIN_EDIT if operation == "update" else ORIGIN_NEW,
        "original_name": original_name,
        "name": args["name"],
        "description": args["description"],
        "params": args["params"],
        "script": args["script"],
        "review": None,
    })
    return edited_draft


def build_calculation_tools(
    calculations_client: CalculationsApiClient,
    reviewer_client: ReviewerApiClient,
):
    @tool
    async def search_calculations(queries: list[str]) -> str:
        """Search custom calculations by one or more name/description fragments in a
        single call. Returns lean summaries (name + description) with total counts.
        An empty string or "*" matches all calculations."""
        try:
            results = await calculations_client.bulk_search(queries)
        except UpstreamServiceError as exc:
            return f"Error: {exc.message}"

        lines = []
        for entry in results:
            matches = "; ".join(
                f"{match['name']} - {match['description']}" for match in entry["matches"]
            ) or "(none)"
            lines.append(f"'{entry['query']}': {matches} (total {entry['total']})")
        return "\n".join(lines)

    @tool
    async def get_calculation(name: str) -> str:
        """Get a calculation's description, params, and status - call this before
        execute_calculation to map the user's inputs to the declared params."""
        try:
            calculation = await calculations_client.get(name)
        except UpstreamServiceError as exc:
            return f"Error: {exc.message}"

        return (
            f"Calculation '{calculation['name']}' ({calculation['reviewStatus']}):\n"
            f"Description: {calculation['description']}\n"
            f"Params:\n{_params_text(calculation['params'])}"
        )

    @tool
    async def execute_calculation(name: str, params: dict[str, float]) -> str:
        """Execute a saved calculation with numeric values for ALL of its declared
        params, e.g. execute_calculation("gp_sum", {"a": 2, "r": 3, "n": 4})."""
        try:
            outcome = await calculations_client.execute(name, params)
        except UpstreamServiceError as exc:
            return f"Error: {exc.message}"

        return f"Results: {outcome['results']} (took {outcome['durationMs']:.0f} ms)"

    @tool
    async def delete_calculation(name: str) -> str:
        """Delete a saved calculation by name. The system asks the user to confirm."""
        try:
            deleted = await calculations_client.delete(name)
        except UpstreamServiceError as exc:
            return f"Error: {exc.message}"

        return (
            f"Calculation '{name}' deleted."
            if deleted
            else f"Error: calculation '{name}' not found."
        )

    @tool
    async def author_calculation(
        prompt: str,
        tool_call_id: Annotated[str, InjectedToolCallId],
        name: str | None = None,
    ) -> Command | str:
        """Author a NEW custom calculation from a plain-language description of what it
        must compute. The system generates and reviews the script (never write script
        code yourself). The result becomes the current draft for the user to approve."""
        try:
            authored = await reviewer_client.author(prompt=prompt, name=name)
        except UpstreamServiceError as exc:
            return f"Error: {exc.message}"

        draft = {
            "name": authored["name"],
            "description": authored["description"],
            "script": authored["script"],
            "params": authored["params"],
            "review": authored["review"],
            "origin": ORIGIN_NEW,
            "original_name": None,
        }
        return _draft_command(draft, _format_draft(draft), tool_call_id)

    @tool
    async def load_calculation(
        name: str,
        tool_call_id: Annotated[str, InjectedToolCallId],
    ) -> Command | str:
        """Load an EXISTING calculation into the draft to edit it (rename, change
        description, or revise behavior). Follow with revise_draft for requested functional changes."""
        try:
            calculation = await calculations_client.get(name)
        except UpstreamServiceError as exc:
            return f"Error: {exc.message}"

        draft = {
            "name": calculation["name"],
            "description": calculation["description"],
            "script": calculation["script"],
            "params": calculation["params"],
            "review": calculation.get("reviewNotes"),
            "origin": ORIGIN_EDIT,
            "original_name": calculation["name"],
        }
        return _draft_command(draft, _format_draft(draft), tool_call_id)

    @tool
    async def revise_draft(
        instructions: str,
        state: Annotated[dict, InjectedState],
        tool_call_id: Annotated[str, InjectedToolCallId],
    ) -> Command | str:
        """Functionally change the current draft (different behavior, new/changed
        params, fixes for review issues). The system regenerates and re-reviews the
        script based on the instructions; the result replaces the draft."""
        draft = state.get("calculation_draft")
        if not draft:
            return "Error: no draft to revise - author_calculation or load_calculation first."

        prompt = (
            "Modify the following existing calculation.\n"
            f"Current name: {draft['name']}\n"
            f"Current description: {draft['description']}\n"
            f"Current params:\n{_params_text(draft['params'])}\n"
            f"Current script:\n{draft['script']}\n\n"
            f"Requested change: {instructions}\n"
            "Produce the complete improved calculation."
        )

        try:
            authored = await reviewer_client.author(
                prompt=prompt, name=draft["name"], params_hint=draft["params"]
            )
        except UpstreamServiceError as exc:
            return f"Error: {exc.message}"

        revised = {
            **draft,
            "name": authored["name"],
            "description": authored["description"],
            "script": authored["script"],
            "params": authored["params"],
            "review": authored["review"],
        }
        return _draft_command(revised, _format_draft(revised), tool_call_id)

    @tool
    async def save_calculation(
        state: Annotated[dict, InjectedState],
        tool_call_id: Annotated[str, InjectedToolCallId],
    ) -> Command | str:
        """Persist the current draft after explicit runtime approval.

        Before calculator-service is called, execution is interrupted and the complete
        calculation is presented for approve, edit, or reject. An edit is submitted
        directly to calculator-service without another approval cycle.
        """
        draft = state.get("calculation_draft")
        if not draft:
            return "Error: no draft to save - author_calculation or load_calculation first."

        resume_value = interrupt(_build_save_interrupt_payload(draft))

        try:
            decision_type, edited_args, feedback = _extract_save_decision(resume_value)
        except ValueError as exc:
            return _draft_command(draft, f"Error: {exc}", tool_call_id)

        if decision_type == "reject":
            message = "Calculation save rejected."
            if feedback:
                message += f" User feedback: {feedback}"
            return _draft_command(draft, message, tool_call_id)

        submitted_draft = draft
        if decision_type == "edit":
            try:
                submitted_draft = _draft_from_save_arguments(draft, edited_args or {})
            except ValueError as exc:
                return _draft_command(draft, f"Error: {exc}", tool_call_id)

        try:
            if submitted_draft["origin"] == ORIGIN_EDIT:
                payload = {
                    "description": submitted_draft["description"],
                    "script": submitted_draft["script"],
                    "params": submitted_draft["params"],
                }
                if submitted_draft["name"] != submitted_draft["original_name"]:
                    payload["name"] = submitted_draft["name"]

                saved = await calculations_client.update(
                    submitted_draft["original_name"], payload
                )
            else:
                saved = await calculations_client.create(
                    submitted_draft["name"],
                    submitted_draft["description"],
                    submitted_draft["script"],
                    submitted_draft["params"],
                )
        except UpstreamServiceError as exc:
            return _draft_command(submitted_draft, f"Error: {exc.message}", tool_call_id)

        status = saved.get("reviewStatus")
        message = f"Saved calculation '{saved['name']}' (review status: {status})."

        if feedback:
            message += f" User message: {feedback}"

        if status != "APPROVED":
            issues = (saved.get("reviewNotes") or {}).get("issues", [])
            issue_text = "; ".join(
                issue.get("message", "") for issue in issues
            ) or "see review notes"
            message += f" It is DISABLED until fixed: {issue_text}"

        return _draft_command(None, message, tool_call_id)

    return [
        search_calculations,
        get_calculation,
        execute_calculation,
        delete_calculation,
        author_calculation,
        load_calculation,
        revise_draft,
        save_calculation,
    ]
