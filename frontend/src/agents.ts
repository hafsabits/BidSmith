import { Pipeline } from "./api";

export const AGENT_INFO: Record<string, { name: string; does: string }> = {
  analyst: { name: "RFP Analyst", does: "Reads the solicitation and pulls out scope, size, location, budget, and requirements." },
  fit: { name: "Bid / No-Bid", does: "Scores the fit against Ryan's own project history and competitors' awards." },
  human_review: { name: "Your decision", does: "Approve or override the bid recommendation." },
  estimator: { name: "Estimator", does: "Prices the work with the cost engine (AACE Class 5/4, by CSI division)." },
  risk: { name: "Risk", does: "Runs rule checks and reviews the contract for risks." },
  writer: { name: "Proposal Writer", does: "Drafts the proposal, citing only Ryan's own projects." },
};

export const RUN_OPTIONS: { value: Pipeline; label: string; hint: string }[] = [
  { value: "full", label: "All agents, step by step", hint: "Pauses after each agent so you can review before continuing." },
  { value: "analyst", label: "RFP Analyst only", hint: "Just the structured reading of the RFP." },
  { value: "fit", label: "Bid / No-Bid only", hint: "Reads the RFP, then scores the fit." },
  { value: "estimator", label: "Estimator only", hint: "Reads the RFP, then prices it. Or enter the parameters yourself." },
  { value: "risk", label: "Risk only", hint: "Reads the RFP, then builds a risk register." },
  { value: "writer", label: "Proposal Writer only", hint: "Reads the RFP, then drafts a proposal (no pricing)." },
];
