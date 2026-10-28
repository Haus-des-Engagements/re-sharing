# 0025. Shared Accounting Client

Date: 2026-10-28

## Status

Accepted

## Context

Four booking tasks each built their own HTTP request to the accounting system: credentials, headers, timeout and error handling were copied four times. The agreements app needs the same system for return invoices, receipts and bank transactions.

## Decision

`re_sharing/utils/buchhaltungsbutler.py` is the only module that talks to the accounting system. It exposes `create_draft_invoice`, `create_einvoice`, `get_receipts` and `get_transactions`, pages list endpoints, and raises one `BuchhaltungsButlerError` for network errors, HTTP errors, missing JSON and responses with `success: false`; the API's message is kept on the error. Callers build payloads and decide what an error means for them. The booking tasks keep their names and results.

Return invoices use `create_einvoice`, which already returns the invoice number for bookings.

## Consequences

- Tests mock the client functions instead of `requests`.
- The endpoints and filters of `get_receipts` and `get_transactions` follow the API documentation and should be checked against the live system before the first nightly run.
