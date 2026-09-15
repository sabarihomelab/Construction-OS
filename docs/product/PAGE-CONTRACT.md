# Construction OS Page Contract

Every product page is designed before implementation using the same contract. This prevents inconsistent screens, hard-coded behavior and undocumented access rules.

## Page Identity

- page name
- route
- module
- primary object
- related objects
- purpose
- target user personas

## Access

- feature flag / tenant module requirement
- page-view capability
- action capabilities
- project/company scope requirements
- sensitive-data requirements
- anonymous access allowed: normally no

## Page Content

- header/title
- summary information
- primary actions
- secondary actions
- search
- filters
- sort
- table/list/card controls
- forms
- bulk actions where applicable
- contextual help

## Attributes

For every field shown on a page define:

- source object
- field key
- label
- field type
- required/optional
- visibility
- editability
- validation
- default behavior
- custom-field compatibility
- sensitive-data classification
- help text

## States

Every page must intentionally support:

- empty state
- loading state
- populated state
- validation error
- server/network error
- no permission
- feature disabled
- archived/inactive state where relevant
- offline/reconnect behavior where relevant

No fake production data is used to make an empty screen look complete.

## Responsive Behavior

Define behavior for:

- large desktop
- standard desktop/laptop
- tablet
- phone

Tables must define their small-screen strategy rather than rely on horizontal overflow by accident. Primary actions must remain usable by touch.

## Permission-Driven UI

The page renders from the user's current effective capabilities.

Examples:

- create capability absent -> Create hidden
- edit capability absent -> edit controls hidden
- export capability absent -> Export hidden
- restricted financial field -> field not returned/rendered

The backend remains the enforcement point for every protected action.

## Audit and Events

Define:

- actions that create audit records
- business events emitted
- notification triggers
- approval/workflow transitions

## Help and Documentation

Each page supplies structured help content including:

- what the page is for
- meaning of important terms
- meaning of fields/actions
- workflow explanation
- common questions
- permission explanations
- troubleshooting guidance

This content can power deterministic contextual help and later a private page-aware help assistant.

## Definition of Done

A page is not complete until its real persistence/API behavior, permissions, validation, audit behavior, error/empty states, responsive behavior, tests and help documentation are implemented.
