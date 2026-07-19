# Rotations Cadence & Holidays — Design

**Status:** Approved by user, ready for implementation planning.

## Context

RadSched currently ships a fixed, hardcoded list of 18 services in
`default_services()` (`src/models/service.rs`). There is no UI to add, edit,
or remove a service — doing so requires editing Rust source and rebuilding.
Every service also gets a schedule slot on *every single day of the month*,
regardless of whether it's a daytime-only rotation or a weekend/call
rotation, which both misrepresents the real schedule (weekend call showing
up on Tuesdays) and inflates the solver's penalty score, since
`target_monthly_shifts` (~15-16/attending) assumes far fewer slots than the
~31/attending the current all-days generation produces.

This spec adds a **cadence** to each service (which days it needs a slot at
all), makes services user-manageable through a new "Rotations" tab, and adds
a department-wide **Holidays** list that reclassifies specific weekdays as
weekend-equivalent for cadence purposes — because at this user's site,
holidays run a reduced morning/evening call schedule identical in shape to a
weekend, with all other daytime services off.

## Goals

- Let the scheduler add/edit/remove rotations (services) from the UI, no
  code changes required.
- Each rotation declares which days it needs coverage: every day, weekdays
  only, or weekends only.
- Each rotation declares whether an unfilled slot should count against the
  solver's penalty score (e.g. the optional weekend float should not).
- A department-wide, user-managed list of holiday dates. On a holiday,
  weekday-cadence rotations produce no slots and weekend-cadence rotations
  produce slots exactly as they would on a Saturday/Sunday.

## Non-goals (explicitly out of scope for this pass)

- Arbitrary recurrence rules (every Nth day, first-weekend-of-month, etc.).
  Nothing described needs this; day-type buckets cover every case raised.
- Partial/reduced-hours coverage on holidays (the real spreadsheet shows
  some holiday shifts as "3 hours" instead of a full day) — this spec only
  changes *which* rotations get a slot on a holiday, not shift duration,
  which the app doesn't model at all today.
- Recurring annual holidays (e.g. auto-applying "July 4th" every year) —
  holidays are entered per date, per year, same granularity as vacations.

## Data model changes

`src/models/service.rs`:

```rust
#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq)]
pub enum ServiceCadence {
    AllDays,
    Weekdays,
    Weekends,
}

pub struct Service {
    pub id: String,
    pub name: String,
    pub category: ServiceCategory,
    pub is_weekend: bool,      // unchanged meaning: counts toward call-eligibility
    pub is_night_call: bool,   //   & call-fairness scoring (see "Relationship to
                                //   existing fields" below)
    pub bundled_with: Option<String>,
    pub description: String,
    pub cadence: ServiceCadence,  // NEW
    pub required: bool,            // NEW
}
```

New file `src/models/holiday.rs`:

```rust
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct Holiday {
    pub id: String,
    pub date: String, // YYYY-MM-DD
    pub name: String, // e.g. "4th of July"
}
```

### Relationship to existing `is_weekend` / `is_night_call`

These two booleans are **not replaced**. They answer a different question
than `cadence`:

- `cadence` — does this rotation need a slot on this particular day at all?
- `is_weekend` / `is_night_call` — does covering this slot require
  `can_cover_call`, and does it count toward the weekend/call fairness
  variance term in `calculate_soft_cost`?

A rotation can in principle have `cadence: Weekends` and
`is_night_call: false` (e.g. a weekend daytime-only role that any
generalist can cover) — keeping the fields independent avoids conflating
"when" with "who's eligible."

## Cadence semantics

New helper in `src/utils/calendar.rs`:

```rust
pub fn is_weekend_or_holiday(year: i32, month: u32, day: u32, holidays: &[Holiday]) -> bool {
    if is_weekend_date(year, month, day) {
        return true;
    }
    let date = format!("{:04}-{:02}-{:02}", year, month, day);
    holidays.iter().any(|h| h.date == date)
}
```

Slot generation in `ScheduleSolver::create_empty_schedule` (holidays becomes
a new field on `ScheduleSolver`, alongside `radiologists`/`services`/
`vacations`):

```rust
let weekend_like = is_weekend_or_holiday(year, month, day, self.holidays);
let include = match svc.cadence {
    ServiceCadence::AllDays => true,
    ServiceCadence::Weekdays => !weekend_like,
    ServiceCadence::Weekends => weekend_like,
};
if include {
    schedule.slots.push(ScheduleSlot::new(&date, day, &svc.id));
}
```

`calculate_soft_cost`'s unassigned-slot penalty (`src/solver/cost.rs`) skips
slots belonging to a non-required service:

```rust
for slot in slots {
    match &slot.assigned_radiologist_id {
        Some(rad_id) => { /* existing shift/weekend counting, unchanged */ }
        None => {
            let required = service_map.get(slot.service_id.as_str())
                .map(|s| s.required)
                .unwrap_or(true);
            if required {
                unassigned_count += 1;
            }
        }
    }
}
```

## UI

### Rotations tab

New `ActiveTab::Rotations` variant + Navbar button ("🔁 Rotations"), new
component `src/components/rotations.rs` (`RotationsManager`), structurally
mirroring `RadiologistsManager`:

- **List panel**: each rotation shown with name, a cadence badge (All days /
  Weekdays / Weekends), a "Required" or "Optional" badge, its bundle target
  if any, and a Remove button.
- **Add-rotation form**: name (text input), cadence (select, defaults to
  Weekdays), required (checkbox, defaults checked), bundles-with (select
  populated from existing rotation names, defaults to none).

New rotations get an id in the same style as `RadiologistsManager::add_radiologist`
but collision-safe (see the companion bug-fix plan — the id-generation fix
applies to both roster and rotation ids).

### Holidays section (same tab, below Rotations)

Reuses the exact interaction pattern `VacationManager` already uses for its
day picker: a day-of-month number input scoped to the currently selected
schedule year/month (same `selected_year`/`selected_month` props passed
into `VacationManager` today), plus a name field, an Add button, and a list
with Remove buttons. No separate month/year inputs — to add a holiday in a
different month, the scheduler switches the grid to that month first, same
as adding a vacation for a future month works today. A select is not needed
since holidays aren't per-radiologist.

Holiday ids are generated as `format!("holiday_{:04}_{:02}_{:02}", year, month, day)`
— derived entirely from the date, not from a mutable list length, so it's
collision-safe by construction (unlike the current vacation/radiologist id
schemes, which the companion bug-fix plan corrects separately).

### Grid rendering

No changes required. `ScheduleGrid` already renders `<td class="slot-cell">"—"</td>`
for any `(service_id, day)` pair with no matching slot (`grid.rs:237-239`),
which is exactly what a cadence-excluded day produces.

## Persistence

`services` and the new `holidays` signal both get LocalStorage persistence
Effects in `app.rs`, following the existing pattern used for `radiologists`
and `vacations` (keys: `radsched_services`, `radsched_holidays`). This also
closes an existing gap: `services` is currently loaded from LocalStorage but
never written back, so `_set_services` has been unused since the app was
bootstrapped — this spec is what that setter was for.

## Migration of existing defaults

`default_services()` (`src/models/service.rs`) is updated to assign cadence
to each of the current 18 entries:

- The 13 `ShiftCoverage` services (am_readout, abd, msk, us, peds, nm,
  chest, er, mammo, lunch, float, evening, general) → `cadence: Weekdays`,
  `required: true`.
- The 5 `CallCoverage` services (nm_call, peds_call, cardiac_call,
  msk_mri_call, trauma_call) → `cadence: Weekends`, `required: true`.

No existing service becomes `required: false` automatically — marking the
weekend float (or any other rotation) optional is a manual edit the
scheduler makes once through the new UI, since only they know which
rotations are actually optional at their site.

## Testing plan

- Unit test in `tests/solver_tests.rs`: a `Weekdays`-cadence service
  produces zero slots on a Saturday; a `Weekends`-cadence service produces a
  slot on a designated holiday that falls on a Wednesday, and zero slots on
  a non-holiday Wednesday.
- Unit test: an unfilled `required: false` slot contributes zero to
  `calculate_soft_cost`, where the same slot with `required: true` con
  tributes 500.
- Manual UI check: add a new rotation from the Rotations tab, confirm it
  appears in the generated schedule grid on the correct days without
  restarting/rebuilding the app; add a holiday date, confirm a
  `Weekdays`-cadence service disappears from the grid that day and a
  `Weekends`-cadence one appears.

## Open items for the implementation plan (not this spec)

This spec covers the rotations/cadence/holidays feature only. It depends on
— and should be sequenced after — the separate data-loss bug fix (the
schedule-rebuilding `Effect` in `app.rs` currently wipes the schedule on any
`services`/`radiologists`/`vacations` change, which would make manually
testing this feature painful until fixed).
