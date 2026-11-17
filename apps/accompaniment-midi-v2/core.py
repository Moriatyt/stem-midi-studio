"""MIDI routing with absolute-time alignment and source-aware filtering."""
import copy
from pathlib import Path
import pretty_midi

BASE = ('bass', 'guitar', 'keys', 'drums')
LABELS = {'bass':'贝斯', 'guitar':'吉他', 'keys':'键盘', 'drums':'鼓',
          'keys_specialist':'钢琴专用模型补漏', 'other':'残余伴奏中的键盘'}


def family_of(instrument):
    p = instrument.program
    if instrument.is_drum:
        return 'drums'
    if p < 24:
        return 'keys'
    if p < 32:
        return 'guitar'
    if p < 40:
        return 'bass'
    if 80 <= p <= 103:
        return 'keys'  # Synth leads, pads and keyboard effects belong to keys.
    return None  # choir, voice and unsupported instruments


def export_sources(sources, destination, bpm=120, minimum_ms=0):
    """sources: [(role, MIDI path)]. All stems must share a zero point.

    Dedicated stems accept their family. Residual audio is checked for keys
    only. The piano specialist also contributes keys. Cross-source keyboard
    duplicates are removed without collapsing chords or repeated attacks.
    """
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=True)
    # A resumed job may contain an export made before strings were disabled.
    for name in (*BASE,'strings','brass','woodwinds','timpani','orchestra_hit','synth'):
        stale = destination / f'{name}.mid'
        if stale.is_file():
            stale.unlink()
    groups = {key: [] for key in BASE}
    discarded, short, duplicates = 0, 0, 0
    key_candidates = []
    reference = None
    for role, path in sources:
        midi = pretty_midi.PrettyMIDI(str(path))
        if reference is None:
            reference = midi
        for index, instrument in enumerate(midi.instruments):
            family = family_of(instrument)
            allowed = family is not None
            if role in BASE:
                allowed = family == role
            elif role in ('other','keys_specialist'):
                allowed = family == 'keys'
            if not allowed:
                discarded += len(instrument.notes)
                continue
            track = copy.deepcopy(instrument)
            track.name = f'{family}_{pretty_midi.program_to_instrument_name(track.program)}_{role}_{index}'
            kept = [n for n in track.notes if n.end > n.start and (n.end-n.start)*1000 >= minimum_ms]
            short += len(track.notes) - len(kept)
            track.notes = sorted(kept, key=lambda n: (n.start, n.pitch))
            if kept:
                if family == 'keys':
                    key_candidates.append((role, track))
                else:
                    groups[family].append(track)
    accepted = {pitch: [] for pitch in range(128)}
    # Prefer dedicated keyboard estimates over additional residual estimates.
    for role, track in sorted(key_candidates, key=lambda item: {'keys':0,'keys_specialist':1,'other':2}.get(item[0],0)):
        kept = []
        for note in track.notes:
            duplicate = any(old_role != role and abs(old.start-note.start) <= .04
                            and min(old.end,note.end)-max(old.start,note.start) >= .7*min(old.end-old.start,note.end-note.start)
                            for old_role, old in accepted[note.pitch])
            if duplicate:
                duplicates += 1
            else:
                kept.append(note)
                accepted[note.pitch].append((role,note))
        track.notes = kept
        if kept:
            groups['keys'].append(track)
    # A single source keeps its original tempo map. Multiple independent
    # predictions use one explicit tempo; note/event seconds stay unchanged.
    combined = copy.deepcopy(reference) if len(sources) == 1 else pretty_midi.PrettyMIDI(initial_tempo=bpm, resolution=960)
    combined.instruments = []
    counts = {}
    for family, tracks in groups.items():
        counts[family] = sum(len(t.notes) for t in tracks)
        if not tracks:
            continue
        combined.instruments.extend(tracks)
        single = copy.deepcopy(combined)
        single.instruments = copy.deepcopy(tracks)
        single.write(str(destination / f'{family}.mid'))
    combined.write(str(destination / 'accompaniment.mid'))
    return {'notes': counts, 'discarded_notes': discarded, 'short_notes_removed': short, 'keyboard_duplicates_removed': duplicates,
            'tempo_mode': 'original' if len(sources) == 1 else f'fixed {bpm} BPM; absolute timing preserved'}
