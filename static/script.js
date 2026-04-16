const video = document.getElementById('video');
const captureBtn = document.getElementById('captureBtn');
const resultDiv = document.getElementById('result');
const subjectSelect = document.getElementById('subjectSelect');
let isCapturing = false;

navigator.mediaDevices.getUserMedia({ video: true })
    .then(stream => { video.srcObject = stream; })
    .catch(err => { resultDiv.innerHTML = 'Camera error: ' + err.message; });

function captureFrame() {
    return new Promise((resolve) => {
        const canvas = document.createElement('canvas');
        canvas.width = video.videoWidth;
        canvas.height = video.videoHeight;
        const ctx = canvas.getContext('2d');
        ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
        canvas.toBlob(resolve, 'image/jpeg', 0.8);
    });
}

async function captureAndRecognize() {
    if (isCapturing) return;
    const subjectId = subjectSelect.value;
    if (!subjectId) {
        resultDiv.innerHTML = 'Please select a subject first.';
        return;
    }
    
    isCapturing = true;
    resultDiv.innerHTML = '📸 Capturing frames for liveness...<br>' + resultDiv.innerHTML;
    
    const frames = [];
    for (let i = 0; i < 5; i++) {
        const blob = await captureFrame();
        frames.push(blob);
        await new Promise(r => setTimeout(r, 200)); // 200ms between frames
    }
    
    const formData = new FormData();
    frames.forEach((blob, idx) => {
        formData.append(`frame${idx}`, blob, `frame${idx}.jpg`);
    });
    formData.append('subject_id', subjectId);
    
    try {
        const response = await fetch('/teacher/attendance/recognize_liveness', {
            method: 'POST',
            body: formData
        });
        const data = await response.json();
        const timestamp = new Date().toLocaleTimeString();
        if (data.recognized) {
            let msg = `[${timestamp}] ✅ ${data.name} (${data.subject}) - ${data.already_marked ? 'Already marked' : 'Marked!'}`;
            resultDiv.innerHTML = msg + '<br>' + resultDiv.innerHTML;
        } else {
            resultDiv.innerHTML = `[${timestamp}] ❌ ${data.reason}<br>` + resultDiv.innerHTML;
        }
        // Keep last 10 lines
        let lines = resultDiv.innerHTML.split('<br>');
        if (lines.length > 10) resultDiv.innerHTML = lines.slice(0,10).join('<br>');
    } catch (err) {
        resultDiv.innerHTML = `[${new Date().toLocaleTimeString()}] Error: ${err.message}<br>` + resultDiv.innerHTML;
    }
    isCapturing = false;
}

captureBtn.onclick = captureAndRecognize;