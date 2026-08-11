# Signal Notes autonomous micro project

## Original objective

Build a small local web application called Signal Notes.

A user must be able to create a note, see it immediately, reload the page and still see it, delete it, and receive a clear validation message when attempting to add an empty note.

The application must start locally with one command and the complete user journey must be verified in a real browser.

## Acceptance criteria

1. The application opens in a browser and presents a clear note entry interface.
2. A note can be created and becomes visible without a manual page refresh.
3. The created note remains visible after a browser reload.
4. The note can be deleted and remains absent after another reload.
5. Submitting an empty note produces a visible validation message and does not create a blank record.
6. The interface has accessible labels and controls that can be operated through browser automation.
7. The application has one documented local start command and honors the `PORT` environment variable when it is set.
8. Runtime evidence, the connected browser journey, and independent verification are recorded through Company OS before the mission is accepted.

## Constraints

1. Work only inside the isolated test workspace.
2. Do not use external services, hosted databases, deployment, payments, or production credentials.
3. Prefer existing platform capabilities, the standard library, and already installed tools before adding code or dependencies.
4. Do not simplify away validation, persistence, accessibility, error handling, tests, or any acceptance criterion.
5. Planning and documentation do not count as progress unless they directly unblock the active route.
6. Keep the implementation appropriately small for this objective.
