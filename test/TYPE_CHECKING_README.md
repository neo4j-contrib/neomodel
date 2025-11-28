# Type Checking Tests for Neomodel

This directory contains type checking tests that verify the correctness of neomodel's type stubs.

## What are Type Stubs?

Type stubs (`.pyi` files) provide type information for Python libraries, enabling:
- **Static type checking** with mypy
- **Better IDE autocomplete** and error detection
- **Improved code documentation** through types

## Test File: `test_typing.py`

This file contains type-checking tests that verify:
1. ✅ Property types are correctly inferred (`person.name` → `str`)
2. ✅ Type errors are caught (`person.name` assigned to `int` variable)
3. ✅ Class-level access returns property descriptors
4. ✅ String/numeric operations work correctly
5. ✅ NodeSet operations type-check

**Important:** This file is NOT meant to be run with pytest! It's analyzed statically by mypy.

## Running Type Checks Locally

```bash
# Run mypy on the typing test file
mypy test/test_typing.py --config-file pyproject.toml
```

**Expected output:**
- ✅ If you see errors from `out/neomodel/*.pyi` - **This is fine!**
  - These are internal stub file errors
  - They don't affect user code
  - The important thing is whether test_typing.py passes
- ❌ If you see errors from `test/test_typing.py` - **This is a problem!**
  - Means type inference is broken
  - Needs to be fixed before merging

**What we're checking:**
We're NOT checking if stub files are perfect internally. We're checking if they **work correctly for users**. The test file represents user code, and as long as it type-checks, the stubs are doing their job.

## CI/CD Integration

Type checking runs automatically on every PR via GitHub Actions (`.github/workflows/type-checking.yml`).

The workflow:
- Runs on Python 3.10, 3.11, 3.12, and 3.13
- Verifies type stubs are syntactically correct
- Ensures type inference works for common patterns
- Catches regressions in type stub accuracy

## What Gets Checked

### ✅ Core Property Types
- `StringProperty` → `str`
- `IntegerProperty` → `int`
- `FloatProperty` → `float`
- `BooleanProperty` → `bool`
- `DateProperty` → `date`
- `DateTimeProperty` → `datetime`
- `ArrayProperty` → `list`
- `JSONProperty` → `Any`
- `UniqueIdProperty` → `str`

### ✅ Type Safety
The tests verify that mypy catches type errors:
```python
person.age = "thirty"  # Error: str incompatible with int
wrong: int = person.name  # Error: str incompatible with int
```

## Maintaining Type Stubs

When modifying neomodel's property system:
1. Update the type stubs in `out/neomodel/*.pyi`
2. Run `mypy test/test_typing.py` to verify
3. Add new test cases to `test_typing.py` for new property types
4. Push and let CI verify across all Python versions

## Why Not Runtime Tests?

Type stubs are checked **statically** (without executing code), which means:
- ⚡ Faster feedback (no Neo4j instance needed)
- 🔍 Catches type errors before runtime
- 🎯 Tests type inference, not behavior

Runtime behavior is tested separately by the integration tests.

## References

- [PEP 561 - Distributing and Packaging Type Information](https://peps.python.org/pep-0561/)
- [mypy Documentation](https://mypy.readthedocs.io/)
- [Issue #473 - Add typing annotations](https://github.com/neo4j-contrib/neomodel/issues/473)
