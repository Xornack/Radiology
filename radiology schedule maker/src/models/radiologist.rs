use serde::{Deserialize, Serialize};
use std::collections::HashSet;

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct Radiologist {
    pub id: String,
    pub name: String,
    pub initials: String,                     // e.g. "MH", "ROB", "SBO"
    pub allowed_services: HashSet<String>, // Service IDs
    pub can_cover_call: bool,                 // Eligible for call
    pub target_monthly_shifts: u32,           // Target shifts
    pub color_code: String,                   // Badge color
    pub owed_days_notes: String,              // e.g. "+2 Days for Aug 3rd Call"
}

impl Radiologist {
    pub fn new(id: impl Into<String>, name: impl Into<String>, initials: impl Into<String>, allowed_services: Vec<&str>, can_cover_call: bool) -> Self {
        let services_set = allowed_services.into_iter().map(|s| s.to_string()).collect();
        Self {
            id: id.into(),
            name: name.into(),
            initials: initials.into(),
            allowed_services: services_set,
            can_cover_call,
            target_monthly_shifts: 16,
            color_code: "#6366f1".to_string(),
            owed_days_notes: String::new(),
        }
    }

    pub fn covers_service(&self, service_id: &str) -> bool {
        self.allowed_services.contains(service_id) || self.allowed_services.contains("ALL")
    }

    pub fn display_badge(&self) -> String {
        if !self.initials.is_empty() {
            self.initials.clone()
        } else {
            let parts: Vec<&str> = self.name.split_whitespace().collect();
            if parts.len() >= 2 {
                format!("{}{}", &parts[0][..1], &parts[1][..1])
            } else {
                self.name.clone()
            }
        }
    }
}

pub fn default_radiologists() -> Vec<Radiologist> {
    vec![
        Radiologist {
            id: "rad_mh".into(),
            name: "Dr. Matt Harwood".into(),
            initials: "MH".into(),
            allowed_services: vec!["msk".into(), "am_readout".into(), "msk_mri_call".into()].into_iter().collect(),
            can_cover_call: true,
            target_monthly_shifts: 15,
            color_code: "#4f46e5".into(),
            owed_days_notes: "".into(),
        },
        Radiologist {
            id: "rad_sbo".into(),
            name: "Dr. Sean Boone".into(),
            initials: "SBO".into(),
            allowed_services: vec!["ALL".into()].into_iter().collect(),
            can_cover_call: true,
            target_monthly_shifts: 16,
            color_code: "#0ea5e9".into(),
            owed_days_notes: "+1 AD Jul 6th".into(),
        },
        Radiologist {
            id: "rad_ab".into(),
            name: "Dr. Amar Bhowra".into(),
            initials: "AB".into(),
            allowed_services: vec!["ALL".into()].into_iter().collect(),
            can_cover_call: true,
            target_monthly_shifts: 16,
            color_code: "#10b981".into(),
            owed_days_notes: "".into(),
        },
        Radiologist {
            id: "rad_al".into(),
            name: "Dr. Andrew Liguori".into(),
            initials: "AL".into(),
            allowed_services: vec!["ALL".into()].into_iter().collect(),
            can_cover_call: true,
            target_monthly_shifts: 16,
            color_code: "#f59e0b".into(),
            owed_days_notes: "+0.5 Day for weekend shift".into(),
        },
        Radiologist {
            id: "rad_th".into(),
            name: "Dr. Tilina Hu".into(),
            initials: "TH".into(),
            allowed_services: vec!["ALL".into()].into_iter().collect(),
            can_cover_call: true,
            target_monthly_shifts: 16,
            color_code: "#ec4899".into(),
            owed_days_notes: "".into(),
        },
        Radiologist {
            id: "rad_nw".into(),
            name: "Dr. Nicole Warrington".into(),
            initials: "NW".into(),
            allowed_services: vec!["ALL".into()].into_iter().collect(),
            can_cover_call: true,
            target_monthly_shifts: 16,
            color_code: "#8b5cf6".into(),
            owed_days_notes: "+1.0 Day for weekend shift (paid off 7/2)".into(),
        },
        Radiologist {
            id: "rad_mm".into(),
            name: "Dr. Michelle Mcquilkin".into(),
            initials: "MM".into(),
            allowed_services: vec!["ALL".into()].into_iter().collect(),
            can_cover_call: true,
            target_monthly_shifts: 16,
            color_code: "#14b8a6".into(),
            owed_days_notes: "+1.5 Days for weekend and grad".into(),
        },
        Radiologist {
            id: "rad_ss".into(),
            name: "Dr. Stephanie Schmeider".into(),
            initials: "SS".into(),
            allowed_services: vec!["ALL".into()].into_iter().collect(),
            can_cover_call: true,
            target_monthly_shifts: 16,
            color_code: "#3b82f6".into(),
            owed_days_notes: "+2.0 Days for weekend shift (1 paid 4/10)".into(),
        },
        Radiologist {
            id: "rad_ok".into(),
            name: "Dr. Olga Kalinkin".into(),
            initials: "OK".into(),
            allowed_services: vec!["ALL".into()].into_iter().collect(),
            can_cover_call: true,
            target_monthly_shifts: 15,
            color_code: "#a855f7".into(),
            owed_days_notes: "".into(),
        },
        Radiologist {
            id: "rad_cm".into(),
            name: "Dr. Corie Mitchell".into(),
            initials: "CM".into(),
            allowed_services: vec!["us".into(), "peds".into(), "am_readout".into()].into_iter().collect(),
            can_cover_call: true,
            target_monthly_shifts: 15,
            color_code: "#06b6d4".into(),
            owed_days_notes: "".into(),
        },
        Radiologist {
            id: "rad_tr".into(),
            name: "Dr. Taruna Ralhan".into(),
            initials: "TR".into(),
            allowed_services: vec!["ALL".into()].into_iter().collect(),
            can_cover_call: true,
            target_monthly_shifts: 16,
            color_code: "#f97316".into(),
            owed_days_notes: "+0.5 Day for weekend shift".into(),
        },
        Radiologist {
            id: "rad_rob".into(),
            name: "Dr. Robert Rivera".into(),
            initials: "ROB".into(),
            allowed_services: vec!["ALL".into()].into_iter().collect(),
            can_cover_call: true,
            target_monthly_shifts: 16,
            color_code: "#ef4444".into(),
            owed_days_notes: "+4.0 Days for weekend shifts (All paid)".into(),
        },
        Radiologist {
            id: "rad_ap".into(),
            name: "Dr. Aileen Park".into(),
            initials: "AP".into(),
            allowed_services: vec!["mammo".into(), "float".into()].into_iter().collect(),
            can_cover_call: false,
            target_monthly_shifts: 14,
            color_code: "#e11d48".into(),
            owed_days_notes: "".into(),
        },
        Radiologist {
            id: "rad_at".into(),
            name: "Dr. Amy Trahan".into(),
            initials: "AT".into(),
            allowed_services: vec!["ALL".into()].into_iter().collect(),
            can_cover_call: true,
            target_monthly_shifts: 16,
            color_code: "#84cc16".into(),
            owed_days_notes: "+2.0 Days for weekend shift".into(),
        },
        Radiologist {
            id: "rad_dk".into(),
            name: "Dr. David Kay".into(),
            initials: "DK".into(),
            allowed_services: vec!["ALL".into()].into_iter().collect(),
            can_cover_call: true,
            target_monthly_shifts: 16,
            color_code: "#10b981".into(),
            owed_days_notes: "+2 Days for Aug 3rd call and May 7th day".into(),
        },
        Radiologist {
            id: "rad_bz".into(),
            name: "Dr. Shane Bezzant".into(),
            initials: "BZ".into(),
            allowed_services: vec!["ALL".into()].into_iter().collect(),
            can_cover_call: true,
            target_monthly_shifts: 15,
            color_code: "#6366f1".into(),
            owed_days_notes: "".into(),
        },
        Radiologist {
            id: "rad_kw".into(),
            name: "Dr. Krichelle White".into(),
            initials: "KW".into(),
            allowed_services: vec!["ALL".into()].into_iter().collect(),
            can_cover_call: true,
            target_monthly_shifts: 15,
            color_code: "#0284c7".into(),
            owed_days_notes: "".into(),
        },
        Radiologist {
            id: "rad_mr".into(),
            name: "Dr. Madisen Rosztoczy".into(),
            initials: "MR".into(),
            allowed_services: vec!["ALL".into()].into_iter().collect(),
            can_cover_call: true,
            target_monthly_shifts: 15,
            color_code: "#d97706".into(),
            owed_days_notes: "".into(),
        },
    ]
}
