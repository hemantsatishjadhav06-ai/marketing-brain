"""Repository layer. Phase 0 routes do queries directly with the dep-injected
Session. Phase 1 moves them into brand-scoped Repository classes that enforce
the no-cross-brand guard at the query layer."""
