# Repair case make-it-faster

Mode **SIMULATED**

[Open pull request for manual review](https://github.com/arice77/hackathoni-companion/pull/1)

Checked PR head `edd27ae98081fe3b70ccfe1b347511c6f2006d33`

| Replay | Revision | Result | Intent calls |
| --- | --- | --- | --- |
| Before | `329cc68aceb40097e6f45e131e7fb5224b15977f` | FAIL | 1 |
| After | `edd27ae98081fe3b70ccfe1b347511c6f2006d33` | PASS | 0 |

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
    "revision": "edd27ae98081fe3b70ccfe1b347511c6f2006d33",
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
