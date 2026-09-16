"""Student enrollment page."""

import numpy as np
import cv2
import pandas as pd
import streamlit as st

from database import db
from ai.detector import detect_faces
from ai.embeddings import build_student_template, serialize_vector


def _uploaded_file_to_bgr(uploaded_file) -> np.ndarray:
    """Decode a Streamlit UploadedFile (upload or camera_input) into a BGR image."""
    file_bytes = np.frombuffer(uploaded_file.getvalue(), dtype=np.uint8)
    return cv2.imdecode(file_bytes, cv2.IMREAD_COLOR)


def render():
    st.header("Student Enrollment")
    st.caption(
        "For this hackathon, only consenting demo participants should be enrolled. "
        "Face images are used only to compute a face template; see Privacy notes below."
    )

    with st.form("enroll_form", clear_on_submit=False):
        col1, col2 = st.columns(2)
        student_id = col1.text_input("Student ID *")
        name = col2.text_input("Student Name *")
        section = st.text_input("Class / Section *", placeholder="e.g. 10-A")

        st.markdown("**Face images** (2–5 clear, front-facing photos recommended)")
        images = st.file_uploader(
            "Upload face images",
            type=["jpg", "jpeg", "png"],
            accept_multiple_files=True,
        )
        camera_shot = st.camera_input("...or capture directly from your webcam")

        submitted = st.form_submit_button("Enroll Student", type="primary")

    if submitted:
        if not student_id or not name or not section:
            st.error("Student ID, Name and Section are required.")
            return
        all_images = list(images) if images else []
        if camera_shot is not None:
            all_images.append(camera_shot)
        if not all_images:
            st.error("Please provide at least one face image (upload or webcam).")
            return

        # --- Run each image through detection, keep the largest face crop ---
        good_crops = []
        skipped = 0
        preview_cols = st.columns(min(len(all_images), 5))
        for i, img_file in enumerate(all_images):
            bgr = _uploaded_file_to_bgr(img_file)
            if bgr is None:
                skipped += 1
                continue
            faces = detect_faces(bgr)
            if not faces:
                skipped += 1
                if i < len(preview_cols):
                    preview_cols[i].image(
                        cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB),
                        caption="No face detected",
                        width='stretch',
                    )
                continue
            if len(faces) > 1:
                st.warning(
                    f"Image {i+1}: {len(faces)} faces detected — using the largest "
                    "one. For best results, use photos with only this student visible."
                )
            best = faces[0]
            good_crops.append(best.gray_crop)
            if i < len(preview_cols):
                x, y, w, h = best.box
                annotated = bgr.copy()
                cv2.rectangle(annotated, (x, y), (x + w, y + h), (0, 200, 0), 2)
                preview_cols[i].image(
                    cv2.cvtColor(annotated, cv2.COLOR_BGR2RGB),
                    caption="Face detected",
                    width='stretch',
                )

        if not good_crops:
            st.error(
                "No usable face was detected in any of the provided images. "
                "Try a clearer, front-facing, well-lit photo."
            )
            return

        template_vec, meta = build_student_template(good_crops)
        db.add_or_update_student(
            student_id=student_id.strip(),
            name=name.strip(),
            section=section.strip(),
            embedding_bytes=serialize_vector(template_vec),
            embedding_meta=meta,
        )
        st.success(
            f"Enrolled **{name}** ({student_id}) in **{section}** using "
            f"{meta['num_samples']} of {len(all_images)} image(s) "
            f"({skipped} skipped — no face detected)."
        )
        st.caption(
            "Only the computed face template was stored — raw photos are discarded "
            "after enrollment, per the privacy guidance below."
        )

    st.divider()
    st.subheader("Enrolled Students")
    students = db.get_all_students()
    if not students:
        st.caption("No students enrolled yet.")
    else:
        df = pd.DataFrame(
            [
                {"Student ID": s["student_id"], "Name": s["name"], "Section": s["section"]}
                for s in students
            ]
        )
        st.dataframe(df, width='stretch', hide_index=True)

        with st.expander("Remove a student"):
            labels = {s["student_id"]: f"{s['name']} ({s['student_id']})" for s in students}
            to_delete = st.selectbox(
                "Student to remove", options=list(labels.keys()),
                format_func=lambda sid: labels[sid],
            )
            confirm = st.checkbox(f"I understand this permanently deletes {labels[to_delete]}'s enrollment.")
            if st.button("Delete student", disabled=not confirm):
                db.delete_student(to_delete)
                st.success(f"Removed {labels[to_delete]}.")
                st.rerun()
