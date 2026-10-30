# Update files for the live demo

Drop **one** Python file here while `main_lipvm_dtsimulation.py` runs: the
visualization's update button becomes clickable, and clicking it submits the
file's updates to the running model. Once submitted, the file is moved to
`applied/`.

An update file defines `UPDATES`, a non-empty list of updates. They are
submitted together as one `AtomicUpdate`: applied at the same checkpoint,
once every part they change is tranquil, all or nothing.

```python
from languages.sysmlv2.updates import ChangeRuntimeAttributeValue

UPDATES = [
    ChangeRuntimeAttributeValue(owner="Main::tokenDepo", attribute="placementCoordinate",
                                new_value=...),
]
```

Ignored here: files whose name starts with `_` or `.`, anything that isn't a
`.py` file (like this README), and subfolders, including `applied/`. Loading
lives in `languages/sysmlv2/update_inbox.py`; the folder can be changed with
`--updates-dir`.
