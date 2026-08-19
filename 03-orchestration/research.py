"""Optional external research stage owned by the orchestration module."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from azure.ai.projects import AIProjectClient
from azure.ai.projects.models import (
    PromptAgentDefinition,
    PromptAgentDefinitionTextOptions,
    TextResponseFormatJsonSchema,
    WebSearchConfiguration,
    WebSearchTool,
    WebSearchToolFilters,
)

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from workshop_core import ConformanceReport, TechnologyResearch

DEFAULT_RESEARCH_AGENT_NAME = "architecture-technology-research-agent"
DEFAULT_RESEARCH_ALLOWLIST = Path(__file__).with_name("research-allowlist.json")


def normalize_allowed_domains(domains: list[str]) -> list[str]:
    normalized: list[str] = []
    for value in domains:
        domain = value.strip().lower().rstrip(".")
        if "://" in domain or "/" in domain or not domain:
            raise ValueError(
                f"Allowed domain must be a hostname without a scheme or path: {value}"
            )
        if domain not in normalized:
            normalized.append(domain)
    return normalized


def load_research_allowlist(path: Path) -> list[str]:
    if not path.is_file():
        raise RuntimeError(f"Research allowlist not found: {path}")
    try:
        config = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise RuntimeError(f"Research allowlist is not valid JSON: {path}") from error
    domains = config.get("allowed_domains") if isinstance(config, dict) else None
    if not isinstance(domains, list) or not all(isinstance(domain, str) for domain in domains):
        raise RuntimeError("Research allowlist must contain an allowed_domains string array")
    normalized = normalize_allowed_domains(domains)
    if not normalized:
        raise RuntimeError("Research allowlist must contain at least one domain")
    return normalized


def url_is_allowed(url: str, allowed_domains: list[str]) -> bool:
    parsed = urlparse(url)
    if parsed.scheme != "https" or not parsed.hostname:
        return False
    hostname = parsed.hostname.lower().rstrip(".")
    return any(
        hostname == domain or hostname.endswith(f".{domain}")
        for domain in allowed_domains
    )


def validate_research(
    research: TechnologyResearch,
    report: ConformanceReport,
    allowed_domains: list[str],
) -> None:
    if research.submission_id != report.submission_id:
        raise ValueError(
            f"Research returned submission {research.submission_id}; "
            f"expected {report.submission_id}"
        )
    if research.technology != report.technology:
        raise ValueError(
            f"Research returned technology {research.technology}; expected {report.technology}"
        )
    for index, claim in enumerate(research.claims, start=1):
        if not url_is_allowed(claim.citation.url, allowed_domains):
            raise ValueError(
                f"Research claim {index} cites a URL outside the allowlist: "
                f"{claim.citation.url}"
            )


def build_research_instructions(allowed_domains: list[str]) -> str:
    domain_list = ", ".join(allowed_domains)
    return f"""You research technologies for an enterprise architecture review.
Use web search for every factual claim. Search and cite only these approved domains:
{domain_list}

Return concise facts that help an architect understand product capabilities, security, support,
deployment, and lifecycle.
- Every claim must have exactly one HTTPS citation from an approved domain.
- Copy the source title and canonical URL from the search result.
- Do not infer facts from a product name.
- If no approved source supports a claim, explain that in the summary and return no claims.
"""


def run_research_agent(
    project_client: AIProjectClient,
    openai_client: Any,
    model_deployment: str,
    agent_name: str,
    report: ConformanceReport,
    connection_id: str,
    allowed_domains: list[str],
    keep_agent: bool = False,
) -> TechnologyResearch:
    agent_version: str | None = None
    conversation_id: str | None = None

    try:
        search_tool = WebSearchTool(
            filters=WebSearchToolFilters(allowed_domains=allowed_domains),
            custom_search_configuration=WebSearchConfiguration(
                project_connection_id=connection_id
            ),
            search_context_size="medium",
        )
        agent = project_client.agents.create_version(
            agent_name=agent_name,
            definition=PromptAgentDefinition(
                model=model_deployment,
                instructions=build_research_instructions(allowed_domains),
                tools=[search_tool],
                tool_choice="required",
                text=PromptAgentDefinitionTextOptions(
                    format=TextResponseFormatJsonSchema(
                        name="TechnologyResearch",
                        schema=TechnologyResearch.model_json_schema(),
                        strict=True,
                    )
                ),
            ),
            description="Researches technologies using approved external domains.",
        )
        agent_version = agent.version
        conversation = openai_client.conversations.create()
        conversation_id = conversation.id
        response = openai_client.responses.create(
            conversation=conversation.id,
            input=(
                f"Research {report.technology} for submission {report.submission_id}. "
                "Return only the structured research result."
            ),
            extra_body={"agent_reference": {"name": agent.name, "type": "agent_reference"}},
        )
        if not response.output_text:
            raise RuntimeError("The research agent returned no text")
        research = TechnologyResearch.model_validate_json(response.output_text)
        validate_research(research, report, allowed_domains)
        cited_domains = {urlparse(claim.citation.url).hostname for claim in research.claims}
        print(
            f"Validated {len(research.claims)} research citations across "
            f"{len(cited_domains)} source domains; all URLs allowlisted",
            file=sys.stderr,
        )
        disposition = "retained" if keep_agent else "cleaned up"
        print(
            f"Research agent: {agent.name} version {agent.version} ({disposition})",
            file=sys.stderr,
        )
        return research
    finally:
        if not keep_agent:
            if conversation_id:
                openai_client.conversations.delete(conversation_id=conversation_id)
            if agent_version:
                project_client.agents.delete_version(
                    agent_name=agent_name,
                    agent_version=agent_version,
                    force=True,
                )
