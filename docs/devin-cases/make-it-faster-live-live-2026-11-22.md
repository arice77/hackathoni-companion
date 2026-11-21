# Repair case make-it-faster-live

Mode **LIVE**

[Open pull request for manual review](https://github.com/arice77/hackathoni-companion/pull/4)

Checked PR head `136ba4585808a2357cbc602fadb7d5f18ecdf17f`

| Replay | Revision | Result | Intent calls |
| --- | --- | --- | --- |
| Before | `329cc68aceb40097e6f45e131e7fb5224b15977f` | FAIL | 1 |
| After | `136ba4585808a2357cbc602fadb7d5f18ecdf17f` | PASS | 0 |

The replay blocks Sarvam requests. Intent calls count attempts, including the blocked baseline attempt.

**Replay evidence**

```json
{
  "before": {
    "revision": "329cc68aceb40097e6f45e131e7fb5224b15977f",
    "passed": false,
    "actual": {
      "kind": "clarify",
      "target_label": null,
      "local_intent": null
    },
    "expected": {
      "kind": "point",
      "target_label": "Settings",
      "local_intent": {
        "action": "speed",
        "speed": "1.25"
      },
      "intent_calls": 0
    },
    "intent_calls": 1
  },
  "after": {
    "revision": "136ba4585808a2357cbc602fadb7d5f18ecdf17f",
    "passed": true,
    "actual": {
      "kind": "point",
      "target_label": "Settings",
      "local_intent": {
        "action": "speed",
        "speed": "1.25"
      }
    },
    "expected": {
      "kind": "point",
      "target_label": "Settings",
      "local_intent": {
        "action": "speed",
        "speed": "1.25"
      },
      "intent_calls": 0
    },
    "intent_calls": 0
  }
}
```
