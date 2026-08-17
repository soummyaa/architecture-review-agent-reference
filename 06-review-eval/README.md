# 06 — Review and Evaluation

## Goal
A critic agent that reviews the draft ADR against the source findings
before a human sees it, plus a small harness that scores output across the
synthetic cases.

## Prerequisites
- 05-adr-generation running successfully

## Run
python 06-review-eval/run.py

## What you should understand by the end
How a review pass reduces hallucination risk, and what "good" means in a
way you can measure rather than assert.
