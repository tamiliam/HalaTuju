# UX Improvement Plan: Smart SPM Result Entry (Mobile-First)

## 1. Problem Analysis
The current implementation uses multiple pairs of `st.selectbox` (Subject + Grade).
*   **Pain Point**: Requires 2 taps per subject + scrolling a long list of 10+ grades.
*   **Cognitive Load**: Users see "Stream Subject 1", "Stream Subject 2" placeholders instead of their actual subjects.
*   **Mobile Issue**: Dropdowns are native system pickers, which can feel "heavy" and disjointed from the app UI on iOS/Android.

## 2. The Solution: "Slide & Select"
We will transform the input flow into a modern, tactile experience.

### A. Subject Selection (The "Cart" Model)
Instead of empty placeholders, let users **search and add** their subjects first.
*   **Component**: `st.multiselect`
*   **Label**: "Add your Elective Subjects"
*   **Behavior**: Users type "Chem" and select "Chemistry". It adds to their list. "Compulsory" subjects are locked/always visible.

### B. Grade Input (The "Slider" Model)
Replace Dropdowns with **`st.select_slider`**.
*   **Why?**:
    *   **Tactile**: Users "swipe" to their grade.
    *   **Visual**: They see the full range (G to A+).
    *   **Faster**: One interaction (drag/click) vs Two (open list, find item).
*   **Layout**:
    *   **Left**: Subject Name (e.g., "History")
    *   **Bottom**: The Slider [G -- D -- C -- ... -- A+]

## 3. Implementation Details

### Step 1: Compulsory Section
Render the 4 core subjects (BM, Eng, Math, Hist) automatically.
*   Use `st.select_slider` for each.
*   Default value: "C" (Center of valid range) or "Not Taken" if applicable? (Core is usually taken). Default to "C" (Passing) is safer than "A+".

### Step 2: Elective Selector
*   **Prompt**: "Select your Stream/Elective subjects:"
*   **Widget**: `st.multiselect` populated with `SUBJ_LIST_SCIENCE + SUBJ_LIST_ARTS`.
*   **Dynamic**: As items are added, new "Cards" appear below for grade entry.

### Step 3: The Grade Card Component
Create a reusable function `render_subject_card(subject_key, subject_name)`:
```python
st.markdown(f"**{subject_name}**")
grade = st.select_slider(
    "Grade",
    options=["G", "E", "D", "C", "C+", "B", "B+", "A-", "A", "A+"],
    value="C",
    key=f"slider_{subject_key}",
    label_visibility="collapsed"
)
```

## 4. UI Polish (CSS)
*   Add custom CSS to style the sliders nicely (make the track thicker/colored?).
*   Group subjects into a "Card" container with a light border/shadow for separation.

## 5. Mobile Preview
![Mockup](mobile_grade_input_mockup.png)
