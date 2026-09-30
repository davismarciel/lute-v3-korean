"""Install Korean into Lute's existing predefined-language catalog."""
from pathlib import Path
import lute


def install_definition(destination=None):
    """Copy the bundled preset into the catalog, refusing conflicting content."""
    root = (
        Path(destination)
        if destination is not None
        else (Path(lute.__file__).parent / "db" / "language_defs")
    )
    target = root / "korean_kiwi" / "definition.yaml"
    content = Path(__file__).with_name("definition.yaml").read_bytes()
    if target.exists() and target.read_bytes() != content:
        raise FileExistsError(f"Refusing to replace a different definition: {target}")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(content)
    return target


def main():
    print(f"Installed Korean definition: {install_definition()}")
    print("Restart Lute, then select Korean in New language.")
