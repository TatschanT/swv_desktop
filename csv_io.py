"""CSV import/export format for the Standing Wave Viewer.

Pure file-format logic with NO Qt (or physics) dependency, so it can be
unit-tested headlessly. The controller (``main.py``) owns the file dialogs and
reads/writes the actual UI widgets; this module only knows the on-disk layout.

Exported file layout (three blank-line-separated sections):
    [Parameters]          - Parameter,Value rows (the ONLY section read on import)
    [Frequency Response]  - Frequency,Relative SPL rows
    [Room Modes]          - Frequency,Mode,Length rows
On import, only ``[Parameters]`` is parsed; the other two sections are ignored.
"""

import csv

# Wall parameter names in export order. The CSV stores them prefixed with "Wall ".
WALL_NAMES = (
    "Left (X=0)", "Right (X=Lx)",
    "Front (Y=0)", "Back (Y=Ly)",
    "Floor (Z=0)", "Ceiling (Z=Lz)",
)


def phase_label_to_index(label):
    """Map an exported phase-correction label back to the combo index.

    Matched case-insensitively by substring so it is robust to label-text
    changes ("Uncorrected"/"Uncorrelated", "Global cancel"/"Global Cancel",
    "True complex field"/"True Complex Field")."""
    low = label.lower()
    if "complex" in low:
        return 2
    if "cancel" in low:
        return 1
    if "uncorre" in low:
        return 0
    raise ValueError(f"Unknown phase correction: {label!r}")


def read_parameters_section(path):
    """Return ``{parameter_name: raw_value_string}`` for the ``[Parameters]``
    section only. Stops at the first blank row or next ``[Section]`` header once
    inside the section. Raises ``ValueError`` if the section or its header row is
    missing/malformed."""
    params = {}
    in_section = False
    header_seen = False
    with open(path, newline="", encoding="utf-8") as fh:
        for row in csv.reader(fh):
            if not in_section:
                if row and row[0].strip() == "[Parameters]":
                    in_section = True
                continue
            # Inside the [Parameters] section.
            if not row or not row[0].strip():
                break  # blank row ends the section
            key = row[0].strip()
            if key.startswith("[") and key.endswith("]"):
                break  # next section header
            if not header_seen:
                if key == "Parameter":
                    header_seen = True
                continue
            if len(row) >= 2:
                params[key] = row[1].strip()

    if not in_section:
        raise ValueError("No [Parameters] section found in the file.")
    if not header_seen:
        raise ValueError("Malformed [Parameters] section (missing header row).")
    return params


def parse_parameters(p):
    """Validate and type-convert the raw parameter strings into a dict ready for
    the controller to apply. Raises ``KeyError`` for a missing key and
    ``ValueError`` for a malformed value -- the caller treats either as a clean
    abort.

    Speaker 2 is required only when ``Source count == 2`` (the export omits it
    for a single source)."""
    def req(key):
        if key not in p:
            raise KeyError(f"Missing parameter: {key}")
        return p[key]

    def as_float(key):
        try:
            return float(req(key))
        except ValueError:
            raise ValueError(f"Invalid number for {key!r}: {p[key]!r}")

    def as_xyz(key):
        parts = req(key).split(",")
        if len(parts) != 3:
            raise ValueError(f"Invalid position for {key!r}: {p[key]!r}")
        try:
            return tuple(float(part) for part in parts)
        except ValueError:
            raise ValueError(f"Invalid position for {key!r}: {p[key]!r}")

    out = {
        "Lx": as_float("Room Lx (m)"),
        "Ly": as_float("Room Ly (m)"),
        "Lz": as_float("Room Lz (m)"),
        "spk1": as_xyz("Speaker 1 (x,y,z)"),
        "mic": as_xyz("Mic (x,y,z)"),
        "walls": {name: as_float(f"Wall {name}") for name in WALL_NAMES},
        "freq": as_float("Frequency (Hz)"),
        "room_scatter": as_float("Room scatter"),
        "listening_area": as_float("Listening area (m)"),
        "phase_index": phase_label_to_index(req("Phase correction")),
    }

    sc = req("Source count").strip()
    if sc not in ("1", "2"):
        raise ValueError(f"Invalid source count: {sc!r}")
    out["num_src"] = int(sc)
    if out["num_src"] == 2:
        out["spk2"] = as_xyz("Speaker 2 (x,y,z)")
    return out


def load_parameters(path):
    """Read + parse the ``[Parameters]`` section from ``path`` in one call.

    Raises ``OSError`` (unreadable file), ``ValueError`` (malformed) or
    ``KeyError`` (missing required parameter)."""
    return parse_parameters(read_parameters_section(path))


def write_export(path, *, room, spk1, spk2, mic, num_src, walls, freq,
                 corr_mode, room_scatter, listening_area,
                 response_freqs, response_db, modes):
    """Write the full export CSV to ``path``. Raises ``OSError`` on write failure.

    ``walls`` maps each ``WALL_NAMES`` entry to its coefficient. ``response_db``
    may be ``None`` (the frequency-response rows are then skipped). ``modes`` is
    an iterable of ``(freq, (nx, ny, nz), length)``. The layout matches what
    ``read_parameters_section`` expects on re-import."""
    with open(path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)

        # --- Section 1: parameters -----------------------------------
        writer.writerow(["[Parameters]"])
        writer.writerow(["Parameter", "Value"])
        writer.writerow(["Room Lx (m)", f"{room.Lx:.3f}"])
        writer.writerow(["Room Ly (m)", f"{room.Ly:.3f}"])
        writer.writerow(["Room Lz (m)", f"{room.Lz:.3f}"])
        writer.writerow(["Speaker 1 (x,y,z)", f"{spk1.x:.3f}, {spk1.y:.3f}, {spk1.z:.3f}"])
        if num_src == 2:
            writer.writerow(["Speaker 2 (x,y,z)", f"{spk2.x:.3f}, {spk2.y:.3f}, {spk2.z:.3f}"])
        writer.writerow(["Mic (x,y,z)", f"{mic.x:.3f}, {mic.y:.3f}, {mic.z:.3f}"])
        writer.writerow(["Reflection Rx", f"{room.Rx:.3f}"])
        writer.writerow(["Reflection Ry", f"{room.Ry:.3f}"])
        writer.writerow(["Reflection Rz", f"{room.Rz:.3f}"])
        for name in WALL_NAMES:
            writer.writerow([f"Wall {name}", f"{walls[name]:.2f}"])
        writer.writerow(["Frequency (Hz)", f"{freq:.1f}"])
        writer.writerow(["Source count", num_src])
        writer.writerow(["Phase correction", corr_mode])
        writer.writerow(["Room scatter", f"{room_scatter:.2f}"])
        writer.writerow(["Listening area (m)", f"{listening_area:.2f}"])

        # --- Section 2: frequency response ---------------------------
        writer.writerow([])
        writer.writerow(["[Frequency Response]"])
        writer.writerow(["Frequency (Hz)", "Relative SPL (dB)"])
        if response_db is not None:
            for f, d in zip(response_freqs, response_db):
                writer.writerow([f"{f:.1f}", f"{d:.3f}"])

        # --- Section 3: room modes -----------------------------------
        writer.writerow([])
        writer.writerow(["[Room Modes]"])
        writer.writerow(["Frequency (Hz)", "Mode (nx, ny, nz)", "Length (m)"])
        for freq_hz, (nx, ny, nz), length in modes:
            writer.writerow([f"{freq_hz:.1f}", f"({nx}, {ny}, {nz})", f"{length:.3f}"])
