# { "Depends": "py-genlayer:1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6" }

import typing
import json
from genlayer import *
from dataclasses import dataclass
import datetime


# ── Storage types ────────────────────────────────────────────────────────────

@allow_storage
@dataclass
class Proposal:
    id:              str
    title:           str
    description:     str
    proposer:        str
    risk_score:      u32    # 0-100  (100 = maximum risk)
    benefit_score:   u32    # 0-100  (100 = maximum benefit)
    recommendation:  str    # ACCEPT | REVISE | REJECT
    required_quorum: u32    # percentage: 51 | 60 | 75
    analysis:        str    # executive summary
    key_risks:       str    # JSON-encoded list
    key_benefits:    str    # JSON-encoded list
    created_at:      str    # ISO timestamp


# ── Contract ─────────────────────────────────────────────────────────────────

class DAORiskScorer(gl.Contract):
    """
    DAO Proposal Risk Scorer — Intelligent Contract on GenLayer.

    Each GenLayer validator independently scores a DAO proposal via LLM,
    then the protocol reaches consensus on the score and recommendation.
    The required quorum for voting is derived automatically from the risk score:
      - risk < 40  → 51% quorum
      - risk 40-69 → 60% quorum
      - risk ≥ 70  → 75% quorum
    """

    proposals:        TreeMap[str, Proposal]
    proposal_counter: u256
    dao_name:         str

    def __init__(self, dao_name: str = "GenLayer DAO"):
        self.proposal_counter = u256(0)
        self.dao_name = dao_name

    # ── helpers ──────────────────────────────────────────────────────────────

    def _quorum_for(self, risk: u32) -> u32:
        r = int(risk)
        if r >= 70:
            return u32(75)
        if r >= 40:
            return u32(60)
        return u32(51)

    def _parse_json(self, raw: str) -> dict:
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            lines = cleaned.split("\n")
            out = []
            skip = True
            for line in lines:
                if skip:
                    skip = False
                    continue
                if line.strip() == "```":
                    break
                out.append(line)
            cleaned = "\n".join(out).strip()
        idx = cleaned.find("{")
        if idx == -1:
            return {}
        depth = 0
        end = -1
        for i in range(idx, len(cleaned)):
            c = cleaned[i]
            if c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
                if depth == 0:
                    end = i + 1
                    break
        if end <= idx:
            return {}
        try:
            return json.loads(cleaned[idx:end])
        except Exception:
            return {}

    def _build_prompt(self, title: str, description: str, full: bool) -> str:
        base = (
            "You are an expert DAO governance analyst.\n\n"
            "Evaluate the following proposal on behalf of the validator network.\n\n"
            "PROPOSAL TITLE: " + title + "\n"
            "PROPOSAL DESCRIPTION:\n" + description + "\n\n"
        )
        if full:
            return (
                base
                + "Return ONLY valid JSON — no prose, no markdown fences:\n"
                "{\n"
                '  "risk_score": <int 0-100>,\n'
                '  "benefit_score": <int 0-100>,\n'
                '  "recommendation": "<ACCEPT|REVISE|REJECT>",\n'
                '  "analysis": "<2-3 sentence executive summary>",\n'
                '  "key_risks": ["<risk>", "<risk>", "<risk>"],\n'
                '  "key_benefits": ["<benefit>", "<benefit>", "<benefit>"]\n'
                "}\n\n"
                "Scoring rules:\n"
                "risk_score 0-30 = low, 31-69 = medium, 70-100 = high\n"
                "benefit_score 0-30 = low, 31-69 = medium, 70-100 = high\n"
                "ACCEPT: risk_score < 40 AND benefit_score > 60\n"
                "REJECT: risk_score > 70 OR benefit_score < 30\n"
                "REVISE: everything else\n"
            )
        else:
            return (
                base
                + "Return ONLY valid JSON:\n"
                "{\n"
                '  "risk_score": <int 0-100>,\n'
                '  "benefit_score": <int 0-100>,\n'
                '  "recommendation": "<ACCEPT|REVISE|REJECT>"\n'
                "}\n"
                "Same scoring rules apply.\n"
            )

    # ── non-deterministic scoring ─────────────────────────────────────────────

    def _score_proposal(self, title: str, description: str) -> dict:

        def leader_fn() -> dict:
            raw = gl.nondet.exec_prompt(
                self._build_prompt(title, description, full=True)
            )
            data = self._parse_json(raw)
            return {
                "risk_score":    max(0, min(100, int(data.get("risk_score",    50)))),
                "benefit_score": max(0, min(100, int(data.get("benefit_score", 50)))),
                "recommendation": str(data.get("recommendation", "REVISE")),
                "analysis":       str(data.get("analysis",       "")),
                "key_risks":      data.get("key_risks",    []),
                "key_benefits":   data.get("key_benefits", []),
            }

        def validator_fn(leaders_res) -> bool:
            if not isinstance(leaders_res, gl.vm.Return):
                return False
            ld = leaders_res.calldata
            raw = gl.nondet.exec_prompt(
                self._build_prompt(title, description, full=False)
            )
            vd = self._parse_json(raw)
            if abs(int(vd.get("risk_score",    50)) - int(ld["risk_score"]))    > 15:
                return False
            if abs(int(vd.get("benefit_score", 50)) - int(ld["benefit_score"])) > 15:
                return False
            return vd.get("recommendation") == ld["recommendation"]

        return gl.vm.run_nondet_unsafe(leader_fn, validator_fn)

    # ── write methods ────────────────────────────────────────────────────────

    @gl.public.write
    def submit_proposal(self, title: str, description: str) -> str:
        assert 5  <= len(title)       <= 200,  "Title: 5–200 chars"
        assert 20 <= len(description) <= 5000, "Description: 20–5000 chars"

        self.proposal_counter = self.proposal_counter + u256(1)
        pid = "PROP-" + str(int(self.proposal_counter)).zfill(4)

        scored = self._score_proposal(title, description)

        risk    = u32(scored["risk_score"])
        benefit = u32(scored["benefit_score"])

        proposal = Proposal(
            id=pid,
            title=title,
            description=description,
            proposer=str(gl.message.sender_address),
            risk_score=risk,
            benefit_score=benefit,
            recommendation=scored["recommendation"],
            required_quorum=self._quorum_for(risk),
            analysis=scored["analysis"],
            key_risks=json.dumps(scored["key_risks"]),
            key_benefits=json.dumps(scored["key_benefits"]),
            created_at=datetime.datetime.now().isoformat(),
        )
        self.proposals[pid] = proposal
        return pid

    # ── view methods ──────────────────────────────────────────────────────────

    @gl.public.view
    def get_proposal(self, proposal_id: str) -> typing.Any:
        if proposal_id not in self.proposals:
            return {}
        p = self.proposals[proposal_id]
        return {
            "id":              p.id,
            "title":           p.title,
            "description":     p.description,
            "proposer":        p.proposer,
            "risk_score":      int(p.risk_score),
            "benefit_score":   int(p.benefit_score),
            "recommendation":  p.recommendation,
            "required_quorum": int(p.required_quorum),
            "analysis":        p.analysis,
            "key_risks":       p.key_risks,
            "key_benefits":    p.key_benefits,
            "created_at":      p.created_at,
        }

    @gl.public.view
    def list_proposals(self) -> list:
        result = []
        for pid, p in self.proposals.items():
            result.append({
                "id":              p.id,
                "title":           p.title,
                "proposer":        p.proposer,
                "risk_score":      int(p.risk_score),
                "benefit_score":   int(p.benefit_score),
                "recommendation":  p.recommendation,
                "required_quorum": int(p.required_quorum),
                "created_at":      p.created_at,
            })
        return result

    @gl.public.view
    def get_stats(self) -> typing.Any:
        total   = int(self.proposal_counter)
        accept  = revise = reject = 0
        avg_r   = avg_b = 0
        for pid, p in self.proposals.items():
            rec = p.recommendation
            if rec == "ACCEPT":
                accept += 1
            elif rec == "REVISE":
                revise += 1
            else:
                reject += 1
            avg_r += int(p.risk_score)
            avg_b += int(p.benefit_score)
        if total > 0:
            avg_r = avg_r // total
            avg_b = avg_b // total
        return {
            "total":       total,
            "accepted":    accept,
            "revised":     revise,
            "rejected":    reject,
            "avg_risk":    avg_r,
            "avg_benefit": avg_b,
            "dao_name":    self.dao_name,
        }

    @gl.public.view
    def get_dao_name(self) -> str:
        return self.dao_name
