use radiology_schedule_maker::models::*;

#[test]
fn derive_initials_two_words_ascii() {
    assert_eq!(derive_initials("Matt Harwood"), "MH");
}

#[test]
fn derive_initials_single_word_returns_first_letter_only() {
    assert_eq!(derive_initials("Cher"), "C");
}

#[test]
fn derive_initials_handles_non_ascii_first_letter() {
    assert_eq!(derive_initials("Émile Zola"), "ÉZ");
}

#[test]
fn display_badge_falls_back_to_full_name_for_single_word() {
    let rad = Radiologist::new("r1", "Cher", "", vec!["ALL"], true);
    assert_eq!(rad.display_badge(), "Cher");
}

#[test]
fn display_badge_uses_explicit_initials_when_set() {
    let rad = Radiologist::new("r1", "Matt Harwood", "MH", vec!["ALL"], true);
    assert_eq!(rad.display_badge(), "MH");
}

#[test]
fn display_badge_derives_from_non_ascii_name_without_panicking() {
    let rad = Radiologist::new("r1", "Émile Zola", "", vec!["ALL"], true);
    assert_eq!(rad.display_badge(), "ÉZ");
}
