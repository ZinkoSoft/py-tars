import io

def test_websocket_receives_dataset_events(client):
    with client.websocket_connect("/ws/events") as ws:
        # Create dataset and expect dataset.created event
        resp = client.post("/datasets", json={"name": "demo"})
        assert resp.status_code == 201
        event = ws.receive_json()
        assert event["type"] == "dataset.created"
        assert event["dataset"] == "demo"
        assert event["metrics"]["clip_count"] == 0

        # Upload recording and expect recording.uploaded
        wav_bytes = b"RIFF....WAVEfmt "
        files = {"file": ("s.wav", io.BytesIO(wav_bytes), "audio/wav")}
        upload_resp = client.post(
            "/datasets/demo/recordings",
            files=files,
            data={"label": "positive"},
        )
        assert upload_resp.status_code == 201
        upload_event = ws.receive_json()
        assert upload_event["type"] == "recording.uploaded"
        clip_id = upload_event["clip_id"]
        assert isinstance(clip_id, str)
        assert upload_event["metrics"]["clip_count"] == 1
        assert upload_event["metrics"]["positives"] == 1

        # Delete recording and expect counts to drop
        del_resp = client.delete(f"/datasets/demo/recordings/{clip_id}")
        assert del_resp.status_code == 200
        delete_event = ws.receive_json()
        assert delete_event["type"] == "recording.deleted"
        assert delete_event["metrics"]["clip_count"] == 0

        # Restore recording and expect counts to return
        restore_resp = client.post(f"/datasets/demo/recordings/{clip_id}/restore")
        assert restore_resp.status_code == 200
        restore_event = ws.receive_json()
        assert restore_event["type"] == "recording.restored"
        assert restore_event["metrics"]["clip_count"] == 1

        # Patch label and ensure redistributed counts
        patch_resp = client.patch(
            f"/datasets/demo/recordings/{clip_id}",
            json={"label": "negative"},
        )
        assert patch_resp.status_code == 200
        patch_event = ws.receive_json()
        assert patch_event["type"] == "recording.updated"
        assert patch_event["metrics"]["negatives"] == 1
        assert patch_event["metrics"]["positives"] == 0


def test_websocket_emits_job_events(client):
    with client.websocket_connect("/ws/events") as ws:
        resp = client.post("/datasets", json={"name": "demo"})
        assert resp.status_code == 201
        ws.receive_json()  # dataset.created

        job_resp = client.post(
            "/train",
            json={"dataset_id": "demo", "config_overrides": {"epochs": 3}},
        )
        assert job_resp.status_code == 202
        job_event = ws.receive_json()
        assert job_event["type"] == "job.queued"
        assert job_event["dataset"] == "demo"
        assert job_event["job_id"] == job_resp.json()["id"]
        assert job_event["metrics"]["clip_count"] == 0

        initial_log_event = ws.receive_json()
        assert initial_log_event["type"] == "job.log"
        assert initial_log_event["job_id"] == job_event["job_id"]
        initial_messages = [entry["message"] for entry in initial_log_event["log_chunk"]["entries"]]
        assert "Job created and queued" in initial_messages

        running_log_event = ws.receive_json()
        assert running_log_event["type"] == "job.log"
        running_messages = [entry["message"] for entry in running_log_event["log_chunk"]["entries"]]
        assert any("Job started" in msg for msg in running_messages)

        running_event = ws.receive_json()
        assert running_event["type"] == "job.running"
        assert running_event["job_id"] == job_event["job_id"]

        completed_log_event = ws.receive_json()
        assert completed_log_event["type"] == "job.log"
        completed_messages = [entry["message"] for entry in completed_log_event["log_chunk"]["entries"]]
        assert "Job completed successfully" in completed_messages

        completed_event = ws.receive_json()
        assert completed_event["type"] == "job.completed"
        assert completed_event["job_id"] == job_event["job_id"]
