# DAO Proposal Risk Scorer

AI-powered DAO governance tool built on **GenLayer Intelligent Contracts**.

Each GenLayer validator independently scores proposals via LLM, then the Optimistic Democracy protocol reaches consensus on the risk score, benefit score, and recommendation. The required voting quorum is derived automatically from the consensus risk score.

## Deployed Contract

| Network    | Address                                     |
|------------|----------------------------------------------|
| Studionet  | `0xCC3952fFef3a9a7a65a9460bE8Ae3Fafc547a71B` |

## How It Works

```
User submits proposal
        ↓
Broadcast to all 5 GenLayer validators
        ↓
Each validator independently: LLM scores risk + benefit
        ↓
Optimistic Democracy consensus (±15 tolerance on scores)
        ↓
Result stored on-chain: risk_score, benefit_score,
recommendation (ACCEPT/REVISE/REJECT), required_quorum,
analysis, key_risks, key_benefits
```

## Quorum Derivation

| Risk Score | Level  | Required Quorum |
|:----------:|:------:|:---------------:|
| 0 – 39     | Low    | **51%**         |
| 40 – 69    | Medium | **60%**         |
| 70 – 100   | High   | **75%**         |

## Repository Structure

```
dao-proposal-risk-scorer/
├── contracts/
│   └── dao_risk_scorer.py   ← GenLayer Intelligent Contract
├── frontend/
│   └── index.html           ← Full frontend (single file, deployed as static site)
└── README.md
```

## Deploy

### 1. Deploy the contract

Open `contracts/dao_risk_scorer.py` in [GenLayer Studio](https://studio.genlayer.com), click **Deploy new instance**. Copy the deployed contract address.

### 2. Update the frontend

In `frontend/index.html`, replace:
```js
const CONTRACT_ADDRESS = 'REPLACE_WITH_DEPLOYED_CONTRACT_ADDRESS';
```
with your deployed address (the current live deployment uses `0xCC3952fFef3a9a7a65a9460bE8Ae3Fafc547a71B`, see [Deployed Contract](#deployed-contract) above).

### 3. Run locally

Serve `frontend/` with any static file server, e.g.:
```bash
npx serve frontend
```
or just open `frontend/index.html` directly in a browser.

### 4. Deploy to Vercel

Deploy the `frontend/` folder as a static site:
```bash
vercel --prod
```

## Contract Methods

### Write
| Method | Args | Description |
|--------|------|-------------|
| `submit_proposal` | `title: str, description: str` | Score a proposal via AI consensus |

### Read
| Method | Args | Returns |
|--------|------|---------|
| `get_proposal` | `proposal_id: str` | Full proposal with scoring |
| `list_proposals` | `offset: u32 = 0, limit: u32 = 0` | All proposals (summary), `limit=0` = no limit |
| `get_stats` | — | Aggregate DAO stats |
| `get_dao_name` | — | DAO name string |

## Tech Stack

- **GenLayer Intelligent Contract** — Python, `gl.vm.run_nondet`, `gl.nondet.exec_prompt`
- **Frontend** — Vanilla JS, `genlayer-js`, Google Fonts (Syne + Inter + JetBrains Mono)
- **Deploy** — Vercel (static site) + GenLayer Studio (contract)
