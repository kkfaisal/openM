"""Agent evaluation suites, logged to MLflow.

Two suites:

``golden``     Offline accuracy. Runs the column-description and
               classification generators against a labelled data dictionary
               and scores them (semantic similarity to the reference,
               sensitivity agreement, exact label match). Each case runs
               twice, without and with RAG context, so the lift from the
               knowledge base is measured directly. The golden file's own
               source is excluded from retrieval to avoid leakage.

``decisions``  Production quality from real reviewer decisions: acceptance
               and edit rates per field, and how well the confidence score
               predicts acceptance (Brier score, expected calibration error).
               No LLM calls.

Run from the API (``POST /api/evals/run``) or the CLI::

    python -m app.evals --suite golden --limit 20
"""
