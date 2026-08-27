# Goal Route Contract

## Goal hierarchy

```text
company goal
  strategy and program goals
    manager goals
      submanager integration goals
        worker leaf goals
```

Every child binds the parent goal ID and digest, names the parent criteria it
advances, inherits constraints and cohesion, narrows authority, and fits the
parent budget and deadline.

## Route hierarchy

```text
root destination
  route version
    sprint
      manager goal
      worker goals
      integration goal
      exit gate
```

A sprint is complete only when its integration goal is accepted. Worker
completion alone cannot advance the route.

## Replanning

Plans and child goals may change. The root goal remains stable.

A reroute receipt records:

1. Old and new route digest.
2. Blocked goal.
3. Concrete blocker.
4. Replacement strategy.
5. Preserved root goal digest.
6. New owner or alternate goal.

## Cohesion

The root goal owns the cohesion contract. Every descendant receives the exact
contract.

Cohesion includes:

1. Strategy thesis.
2. Customer.
3. Brand position.
4. Voice.
5. Design principles.
6. Product principles.
7. Engineering principles.
8. Source of truth paths.

Local optimization that violates cohesion fails integration.
