# AIOAC Screen Map vs Backend Endpoints

Mapping of every route in `frontend/app`, top-level component in `frontend/components/shell`, and FastAPI backend endpoint in `backend/app/routes/`.

---

## 1. Master Screen & Endpoint Inventory

*Legend for Verdict*:
* **KEEP**: Connected to live backend endpoint and reachable in active user flow.
* **SKIP**: Unused/redundant endpoint or unreachable mock remnant.
* **MISSING**: Backend capability exists with no dedicated frontend view/screen.

### Money Flow Screens (`quote` → `approve (hold)` → `train` → `verify` → `capture or void`)

| Screen / Component | Route | Backend Endpoint | Mock / Real | Used in Money Flow? | Verdict |
|---|---|---|---|:---:|:---:|
| **Price Quote** (`QuoteStep`) | `/c/[id]` | `POST /agreements/{pid}/quote`<br>`GET /projects/{pid}` | Real | **YES** (Step 1 - Quote) | **KEEP** |
| **Payment Approval / Hold** (`PayStep`) | `/c/[id]` | `POST /projects/{pid}/quote/approve`<br>`POST /payments/orders` | Real | **YES** (Step 2 - Hold Order) | **KEEP** |
| **PayPal Return Authorization** (`PayReturn`) | `/pay/return` | `POST /payments/{payment_id}/authorize`<br>`POST /projects/{pid}/train` | Real | **YES** (Step 2 - Hold Confirm) | **KEEP** |
| **PayPal Cancel Handler** (`PayCancel`) | `/pay/cancel` | `POST /projects/{pid}/cancel` | Real | **YES** (Step 2 - Hold Cancel) | **KEEP** |
| **Payment Confirmed Transition** (`PaidStep`) | `/c/[id]` | `POST /projects/{pid}/train` | Real | **YES** (Step 3 - Train Launch) | **KEEP** |
| **Training In-Progress** (`TrainingStep`) | `/c/[id]` | `GET /projects/{pid}/training`<br>`POST /projects/{pid}/training/stop` | Real | **YES** (Step 3 - Training) | **KEEP** |
| **Verified Result & Receipt** (`ResultStep`) | `/c/[id]` | `GET /projects/{pid}/training`<br>`GET /projects/{pid}/payment` | Real | **YES** (Step 4 - Verify & Settle) | **KEEP** |
| **Target Missed Result** (`ResultStep`) | `/c/[id]` | `GET /projects/{pid}/training`<br>`GET /projects/{pid}/payment` | Real | **YES** (Step 4 - Compute only, Fee $0) | **KEEP** |
| **User Stopped Result** (`StoppedStep`) | `/c/[id]` | `GET /projects/{pid}/payment` | Real | **YES** (Step 4 - Partial compute) | **KEEP** |
| **System Voided / Failed** (`VoidedStep`) | `/c/[id]` | `GET /projects/{pid}/payment` | Real | **YES** (Step 4 - Hold voided, $0 charged) | **KEEP** |
| **Settlement Retry** (`ResultStep`) | `/c/[id]` | `POST /projects/{pid}/settle/retry` | Real | **YES** (Step 4 - Retry settle) | **KEEP** |

---

### Pre-Money Discovery & Calibration Screens

| Screen / Component | Route | Backend Endpoint | Mock / Real | Used in Money Flow? | Verdict |
|---|---|---|---|:---:|:---:|
| **Goal Prompt / New Project** (`HomeScreen`) | `/` | `POST /projects` | Real | Pre-flow (Goal definition) | **KEEP** |
| **Data Bring & Discovery** (`DataPicker`, `LinkPanel`, `UploadPanel`) | `/c/[id]` | `POST /projects/{pid}/data`<br>`POST /projects/{pid}/data/link`<br>`POST /projects/{pid}/data/{cid}/select` | Real | Pre-flow (Data ingest) | **KEEP** |
| **AI Assistant Chat Loop** (`ChatComposer`, `ChatThread`) | `/c/[id]` | `POST /projects/{pid}/chat`<br>`GET /projects/{pid}/messages`<br>`GET /projects/{pid}/activity` | Real | Pre-flow (Agent guidance) | **KEEP** |
| **Data Readiness Check** (`ReadinessCard`, `ReadinessAction`) | `/c/[id]` | `POST /projects/{pid}/readiness`<br>`GET /projects/{pid}` | Real | Pre-flow (Data grade) | **KEEP** |
| **Free Baseline Test** (`FreeTestAction`) | `/c/[id]` | `POST /projects/{pid}/baseline`<br>`GET /projects/{pid}` | Real | Pre-flow (Zero-cost baseline) | **KEEP** |
| **Target Setting & Free Pilot** (`TargetAction`) | `/c/[id]` | `POST /chats/{pid}/pilot` | Real | Pre-flow (Forecast & confidence) | **KEEP** |
| **Ineligible Forecast & Fix** (`EligibilityCard`) | `/c/[id]` | `POST /chats/{pid}/fix/propose`<br>`POST /chats/{pid}/fix/apply` | Real | Pre-flow (Remedy data issues) | **KEEP** |

---

### Account, Project Management & Public Sharing Screens

| Screen / Component | Route | Backend Endpoint | Mock / Real | Used in Money Flow? | Verdict |
|---|---|---|---|:---:|:---:|
| **Sign Up** (`AuthScreen`) | `/signup` | `POST /auth/signup` | Real | No | **KEEP** |
| **Log In / Demo Auth** (`AuthScreen`) | `/login` | `POST /auth/login`<br>`POST /auth/demo` | Real | No | **KEEP** |
| **User Session / Log Out** (`UserMenu`, `AppShell`) | All routes | `GET /auth/me`<br>`POST /auth/logout` | Real | No | **KEEP** |
| **First-Run Welcome** (`WelcomeScreen`) | `/welcome` | Client-only (static steps) | Static | No | **KEEP** |
| **Projects List** (`ProjectsScreen`) | `/projects` | `GET /projects` | Real | No | **KEEP** |
| **Project Overview** (`ProjectDetail`) | `/projects/[id]` | `GET /projects/{pid}` | Real | No | **KEEP** |
| **Project History Tab** (`ProjectDetail`) | `/projects/[id]?tab=History` | `GET /projects/{pid}/history` | Real | No | **KEEP** |
| **Project Activity Feed Tab** (`ProjectDetail`) | `/projects/[id]?tab=Activity` | `GET /projects/{pid}/activity` | Real | No | **KEEP** |
| **Model Tab: Single Predict** (`ModelTab`) | `/projects/[id]?tab=Model` | `GET /projects/{pid}/model`<br>`POST /projects/{pid}/predict` | Real | No | **KEEP** |
| **Model Tab: Batch Predict (CSV)** (`ModelTab`) | `/projects/[id]?tab=Model` | `POST /projects/{pid}/predict-batch` | Real | No | **KEEP** |
| **Model Tab: Download Weights** (`ModelTab`) | `/projects/[id]?tab=Model` | `GET /projects/{pid}/model/download` | Real | No | **KEEP** |
| **Model Tab: Version Switch** (`ModelTab`) | `/projects/[id]?tab=Model` | `GET /projects/{pid}/model/versions`<br>`POST /projects/{pid}/model/{mid}/use` | Real | No | **KEEP** |
| **Usage Totals** (`UsageScreen`) | `/account/usage` | `GET /account/usage` | Real | No | **KEEP** |
| **Billing History** (`BillingScreen`) | `/account/billing` | `GET /account/payments` | Real | No | **KEEP** |
| **Share Dialog (Owner)** (`ShareDialog`, `ShareButton`) | `/projects/[id]` | `GET /projects/{pid}/share`<br>`POST /projects/{pid}/share`<br>`DELETE /projects/{pid}/share` | Real | No | **KEEP** |
| **Public Result Link** (`PublicResultScreen`) | `/s/[token]` | `GET /public/results/{token}` | Real | No | **KEEP** |

---

### Endpoints Without UI Screens / Unused

| Backend Route / Method | Purpose in Backend | Status | Verdict |
|---|---|---|:---:|
| `GET /projects/{pid}/trace` | DB trace log of agent execution steps | Backend exists; no frontend UI view | **MISSING** (Developer debug screen) |
| `GET /jobs/{pid}/forecast` | Read stored forecast | Handled directly by `POST /chats/{pid}/pilot` & project state | **SKIP** (Duplicate read) |
| `GET /payments/{payment_id}` | Direct payment lookup by payment ID | Frontend uses `GET /projects/{pid}/payment` | **SKIP** (Unused by UI) |
| `POST /webhooks/paypal` | PayPal server-to-server webhook | Background service | **N/A** (Server webhook) |
| `GET /health` | Healthcheck endpoint | Infrastructure probe | **N/A** (Infra only) |

---

## 2. The 8 Screens That Matter Most for the Demo

These 8 screens form the unbroken narrative arc of the product:

1. **Screen 1: Welcome & Auth (`/login` or `/welcome`)**
   * *Purpose*: 1-click Demo sign-in (`POST /auth/demo`) or new account creation.
2. **Screen 2: Goal Prompt (`/`)**
   * *Purpose*: Natural language problem definition ("Which customers may stop buying?").
3. **Screen 3: Data Selection & Agent Proposal (`/c/[id]` — Step 0: `data`)**
   * *Purpose*: Upload CSV, link external dataset (HF/UCI), or let agent find one with approval card.
4. **Screen 4: Data Readiness & Free Baseline (`/c/[id]` — Step 1 & 2: `readiness` & `baseline`)**
   * *Purpose*: Transparent data quality grade (A-F) and free baseline accuracy benchmark before spending anything.
5. **Screen 5: Target Setting & Free Pilot Forecast (`/c/[id]` — Step 3: `target`)**
   * *Purpose*: Sliders/inputs to pick target accuracy, running the free pilot, displaying honest confidence bands.
6. **Screen 6: Transparent Price Quote & PayPal Hold (`/c/[id]` — Step 4: `quote` & `pay`, `/pay/return`)**
   * *Purpose*: Clear price breakdown (Compute cap + Success fee max), PayPal sandbox hold authorization.
7. **Screen 7: Live Training Progress & Stop Control (`/c/[id]` — Step 5: `training`)**
   * *Purpose*: Real-time progress bar, estimated spend so far, and explicit user Stop button.
8. **Screen 8: Verified Result & Money Receipt (`/c/[id]` — Step 6: `result`)**
   * *Purpose*: Independent test set verification ("Target reached"), honest receipt showing compute charged, success fee charged, and held remainder released back to buyer.

