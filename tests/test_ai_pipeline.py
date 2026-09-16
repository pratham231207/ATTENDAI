"""
Tests for ai/detector.py, ai/embeddings.py, ai/recognizer.py.

Uses scikit-image's bundled sample photos (astronaut, camera) as real,
public-domain, different human faces — no network access or download
needed, so these tests run anywhere.
"""

import cv2
import numpy as np
import pytest
from skimage import data

from ai.detector import detect_faces
from ai.embeddings import build_student_template, serialize_vector, deserialize_vector, compute_embedding
from ai.recognizer import match_embedding, chi_square_distance


@pytest.fixture(scope="module")
def astronaut_bgr():
    return cv2.cvtColor(data.astronaut(), cv2.COLOR_RGB2BGR)


def test_detect_faces_finds_a_face(astronaut_bgr):
    faces = detect_faces(astronaut_bgr)
    assert len(faces) >= 1
    x, y, w, h = faces[0].box
    assert w > 0 and h > 0


def test_detect_faces_on_blank_image_returns_empty_list_not_error():
    blank = np.zeros((300, 300, 3), dtype=np.uint8)
    faces = detect_faces(blank)
    assert faces == []


def test_embedding_round_trips_through_serialization(astronaut_bgr):
    crop = detect_faces(astronaut_bgr)[0].gray_crop
    vec = compute_embedding(crop)
    restored = deserialize_vector(serialize_vector(vec))
    assert np.allclose(vec, restored)


def test_same_person_scores_higher_than_different_person(astronaut_bgr):
    """The core recognition sanity check: two photos of the same person
    should score much higher than photos of two different people."""
    crop_a1 = detect_faces(astronaut_bgr)[0].gray_crop
    brightened = cv2.convertScaleAbs(astronaut_bgr, alpha=1.1, beta=15)
    crop_a2 = detect_faces(brightened)[0].gray_crop

    template, _ = build_student_template([crop_a1])
    same_person_vec = compute_embedding(crop_a2)

    cameraman = data.camera()
    different_person_crop = cameraman[60:220, 90:260]  # a different real person
    different_person_vec = compute_embedding(different_person_crop)

    same_distance = chi_square_distance(template, same_person_vec)
    diff_distance = chi_square_distance(template, different_person_vec)

    assert same_distance < diff_distance


def test_match_embedding_accepts_enrolled_match(astronaut_bgr):
    crop = detect_faces(astronaut_bgr)[0].gray_crop
    template, _ = build_student_template([crop])
    enrolled = [{"student_id": "S001", "name": "Rahul", "embedding": serialize_vector(template)}]

    brightened = cv2.convertScaleAbs(astronaut_bgr, alpha=0.9, beta=-10)
    query_crop = detect_faces(brightened)[0].gray_crop
    query_vec = compute_embedding(query_crop)

    result = match_embedding(query_vec, enrolled)
    assert result.is_unknown is False
    assert result.student_id == "S001"


def test_match_embedding_rejects_unenrolled_person(astronaut_bgr):
    crop = detect_faces(astronaut_bgr)[0].gray_crop
    template, _ = build_student_template([crop])
    enrolled = [{"student_id": "S001", "name": "Rahul", "embedding": serialize_vector(template)}]

    cameraman = data.camera()
    different_person_crop = cameraman[60:220, 90:260]
    query_vec = compute_embedding(different_person_crop)

    result = match_embedding(query_vec, enrolled)
    assert result.is_unknown is True
    assert result.student_id is None


def test_match_embedding_with_no_enrolled_students_is_unknown():
    fake_vec = np.random.rand(640).astype(np.float32)
    result = match_embedding(fake_vec, [])
    assert result.is_unknown is True
    assert result.student_id is None


def test_build_student_template_requires_at_least_one_crop():
    with pytest.raises(ValueError):
        build_student_template([])
