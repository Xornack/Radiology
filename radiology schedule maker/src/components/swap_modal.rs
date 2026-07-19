use crate::models::{MonthlySchedule, Radiologist, ScheduleSlot, Service, VacationRequest};
use crate::solver::constraints::HardConstraintChecker;
use leptos::prelude::*;

#[component]
pub fn SwapModal(
    slot: ReadSignal<Option<ScheduleSlot>>,
    on_close: Callback<()>,
    radiologists: ReadSignal<Vec<Radiologist>>,
    services: ReadSignal<Vec<Service>>,
    vacations: ReadSignal<Vec<VacationRequest>>,
    set_schedule: WriteSignal<MonthlySchedule>,
) -> impl IntoView {
    view! {
        {move || {
            if let Some(active_slot) = slot.get() {
                let slot_id = active_slot.id.clone();
                let date = active_slot.date.clone();
                let service_id = active_slot.service_id.clone();
                let current_rad_id = active_slot.assigned_radiologist_id.clone();
                let is_locked = active_slot.is_locked;

                let rads = radiologists.get();
                let svcs = services.get();
                let vacs = vacations.get();

                let svc_name = svcs.iter()
                    .find(|s| s.id == service_id)
                    .map(|s| s.name.as_str())
                    .unwrap_or(&service_id)
                    .to_string();

                let checker = HardConstraintChecker::new(&rads, &svcs, &vacs);

                struct RadCandidate {
                    rad: Radiologist,
                    is_eligible: bool,
                    is_current: bool,
                }

                let candidates: Vec<RadCandidate> = rads.iter().map(|r| {
                    let is_eligible = checker.can_assign(&r.id, &service_id, &date);
                    let is_current = current_rad_id.as_ref() == Some(&r.id);
                    RadCandidate {
                        rad: r.clone(),
                        is_eligible,
                        is_current,
                    }
                }).collect();

                let slot_id_for_lock = slot_id.clone();
                let slot_id_for_clear = slot_id.clone();

                view! {
                    <div class="modal-backdrop" on:click=move |_| on_close.run(())>
                        <div class="modal-card" on:click=move |e| e.stop_propagation()>
                            <div class="modal-header">
                                <div class="modal-title">"🔄 Shift Slot Details & Manual Swap"</div>
                                <button class="btn btn-secondary btn-sm" on:click=move |_| on_close.run(())>"✕ Close"</button>
                            </div>

                            <div style="background: rgba(15, 23, 42, 0.6); padding: 1rem; border-radius: var(--radius-md); border: 1px solid var(--border-color); margin-bottom: 1.25rem;">
                                <div style="font-size: 1.1rem; font-weight: 600; color: var(--secondary);">{svc_name}</div>
                                <div style="font-size: 0.85rem; color: var(--text-muted); margin-top: 0.2rem;">
                                    "📅 Date: " <span style="font-family: var(--font-mono); color: white;">{date.clone()}</span>
                                </div>

                                <div style="display: flex; align-items: center; justify-content: space-between; margin-top: 0.75rem;">
                                    <div>
                                        <span style="font-size: 0.75rem; color: var(--text-dim);">"Current Assignment: "</span>
                                        <span style="font-weight: 600; color: #a5b4fc;">
                                            {current_rad_id.as_ref()
                                                .and_then(|id| rads.iter().find(|r| &r.id == id))
                                                .map(|r| r.name.clone())
                                                .unwrap_or_else(|| "Unassigned".to_string())}
                                        </span>
                                    </div>

                                    <button
                                        class=if is_locked { "btn btn-warning btn-sm" } else { "btn btn-secondary btn-sm" }
                                        on:click=move |_| {
                                            let target_id = slot_id_for_lock.clone();
                                            set_schedule.update(|sched| {
                                                if let Some(s) = sched.slots.iter_mut().find(|s| s.id == target_id) {
                                                    s.is_locked = !s.is_locked;
                                                }
                                            });
                                        }
                                    >
                                        {if is_locked { "🔒 Pinned (Fixed)" } else { "🔓 Pin Assignment" }}
                                    </button>
                                </div>
                            </div>

                            <div class="form-label" style="margin-bottom: 0.6rem;">"Select Eligible Attending to Assign or Swap:"</div>

                            <div style="display: flex; flex-direction: column; gap: 0.5rem; max-height: 300px; overflow-y: auto;">
                                <div
                                    style="background: rgba(15, 23, 42, 0.4); border: 1px dashed var(--border-color); padding: 0.6rem 0.9rem; border-radius: var(--radius-sm); cursor: pointer; display: flex; justify-content: space-between; align-items: center;"
                                    on:click=move |_| {
                                        let target_id = slot_id_for_clear.clone();
                                        set_schedule.update(|sched| {
                                            if let Some(s) = sched.slots.iter_mut().find(|s| s.id == target_id) {
                                                s.assigned_radiologist_id = None;
                                            }
                                        });
                                        on_close.run(());
                                    }
                                >
                                    <span style="font-style: italic; color: var(--text-dim);">"Leave Unassigned"</span>
                                    <span class="btn btn-secondary btn-sm">"Clear"</span>
                                </div>

                                {candidates.into_iter().map(|cand| {
                                    let rad_id = cand.rad.id.clone();
                                    let rad_name = cand.rad.name.clone();
                                    let is_eligible = cand.is_eligible;
                                    let is_current = cand.is_current;
                                    let slot_target_id = slot_id.clone();

                                    let bg = if is_current { "rgba(99, 102, 241, 0.2)" } else if is_eligible { "rgba(15, 23, 42, 0.7)" } else { "rgba(239, 68, 68, 0.1)" };

                                    view! {
                                        <div
                                            style=format!("background: {}; border: 1px solid var(--border-color); padding: 0.6rem 0.9rem; border-radius: var(--radius-sm); display: flex; justify-content: space-between; align-items: center;", bg)
                                        >
                                            <div>
                                                <span style="font-weight: 600;">{rad_name}</span>
                                                {if !is_eligible {
                                                    view! { <span style="font-size: 0.7rem; color: var(--danger); margin-left: 0.5rem;">"❌ Ineligible / PTO"</span> }.into_any()
                                                } else {
                                                    view! { <span style="font-size: 0.7rem; color: var(--success); margin-left: 0.5rem;">"✓ Qualified"</span> }.into_any()
                                                }}
                                            </div>

                                            <button
                                                class="btn btn-primary btn-sm"
                                                disabled=!is_eligible || is_current
                                                on:click=move |_| {
                                                    let s_update = slot_target_id.clone();
                                                    let target_rad = rad_id.clone();
                                                    set_schedule.update(|sched| {
                                                        if let Some(s) = sched.slots.iter_mut().find(|s| s.id == s_update) {
                                                            s.assigned_radiologist_id = Some(target_rad);
                                                        }
                                                    });
                                                    on_close.run(());
                                                }
                                            >
                                                {if is_current { "Currently Assigned" } else { "Assign Attending" }}
                                            </button>
                                        </div>
                                    }
                                }).collect_view()}
                            </div>
                        </div>
                    </div>
                }.into_any()
            } else {
                ().into_any()
            }
        }}
    }
}
