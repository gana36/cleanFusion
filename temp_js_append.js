
// ===========================================
// PDF Extraction Utilities
// ===========================================

function togglePdfExtraction() {
    var section = document.getElementById('pdfExtractionSection');
    var isVisible = section.style.display !== 'none';
    section.style.display = isVisible ? 'none' : 'block';
}

function addPdfInput() {
    var container = document.getElementById('pdfInputsContainer');
    var inputs = container.getElementsByClassName('pdf-input-row');

    if (inputs.length >= 3) {
        alert('Maximum 3 files allowed.');
        return;
    }

    var newRow = document.createElement('div');
    newRow.className = 'pdf-input-row';
    newRow.style.marginBottom = '10px';
    newRow.style.display = 'flex';
    newRow.style.gap = '10px';
    newRow.innerHTML = `
        <input type="file" accept=".pdf" class="pdf-file-input" style="flex: 1; padding: 10px; border: 1px solid #ccc; border-radius: 6px;">
        <button onclick="this.parentElement.remove(); checkAddButton();" style="background: #ff5252; color: white; border: none; padding: 0 10px; border-radius: 6px; cursor: pointer;">✕</button>
    `;
    container.appendChild(newRow);
    checkAddButton();
}

function checkAddButton() {
    var inputs = document.querySelectorAll('.pdf-input-row');
    var btn = document.getElementById('addPdfBtn');
    if (btn) btn.disabled = inputs.length >= 3;
}

async function extractPdfData() {
    var inputs = document.querySelectorAll('.pdf-file-input');
    var files = [];
    inputs.forEach(input => {
        if (input.files[0]) files.push(input.files[0]);
    });

    if (files.length === 0) {
        alert('Please select at least one PDF file.');
        return;
    }

    var resultsContainer = document.getElementById('pdfExtractionResults');
    resultsContainer.innerHTML = '<div style="background: white; padding: 20px; text-align: center; border-radius: 12px;">⏳ Extraction in progress... this may take a minute.</div>';

    var formData = new FormData();
    files.forEach(file => {
        formData.append('files', file);
    });

    // Add current LLM model
    var llmModel = document.getElementById('matchingLLM') ? document.getElementById('matchingLLM').value : '';
    // If not selected or auto, default to a robust model like gemini/claude
    if (!llmModel) llmModel = 'gemini-1.5-flash';
    if (llmModel) formData.append('llm_model', llmModel);

    try {
        var response = await fetch(API_BASE_URL + '/extract_pdf', {
            method: 'POST',
            body: formData
        });

        var result = await response.json();

        resultsContainer.innerHTML = '';

        if (result.success && result.results) {
            result.results.forEach(res => {
                var card = document.createElement('div');
                card.style.background = 'rgba(255,255,255,0.95)';
                card.style.borderRadius = '12px';
                card.style.padding = '16px';
                card.style.backdropFilter = 'blur(10px)';

                var statusIcon = res.success ? '✅' : '❌';
                var statusColor = res.success ? '#2E7D32' : '#c62828';

                var contentHtml = `
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px; border-bottom: 1px solid #eee; padding-bottom: 8px;">
                        <h4 style="margin: 0; color: #333;">${statusIcon} ${res.filename}</h4>
                        <span style="font-size: 12px; color: #666;">${res.elapsed ? res.elapsed.toFixed(1) + 's' : ''}</span>
                    </div>
                `;

                if (res.success && res.extracted_data) {
                    var jsonStr = JSON.stringify(res.extracted_data, null, 2);
                    var hmdCount = res.schema_info ? res.schema_info.hmd_count : 0;
                    var vmdCount = res.schema_info ? res.schema_info.vmd_count : 0;

                    contentHtml += `
                        <div style="font-size: 14px; margin-bottom: 10px;">
                            <strong>Schema:</strong> HMD: ${hmdCount} cols, VMD: ${vmdCount} vars<br>
                            <strong>Fill Rate:</strong> ${res.fill_rate ? res.fill_rate.toFixed(1) : 0}%
                        </div>
                        <details>
                            <summary style="cursor: pointer; color: #1976D2; font-weight: 500;">View Extracted Data</summary>
                            <pre style="background: #f5f5f5; padding: 10px; border-radius: 6px; overflow: auto; max-height: 300px; margin-top: 10px; font-size: 12px;">${jsonStr}</pre>
                        </details>
                    `;
                } else {
                    contentHtml += `<div style="color: ${statusColor};">${res.error || 'Unknown error'}</div>`;
                }

                card.innerHTML = contentHtml;
                resultsContainer.appendChild(card);
            });
        } else {
            resultsContainer.innerHTML = `<div style="background: white; padding: 15px; border-radius: 8px; color: #c62828;">Error: ${result.error || 'Request failed'}</div>`;
        }

    } catch (error) {
        resultsContainer.innerHTML = `<div style="background: white; padding: 15px; border-radius: 8px; color: #c62828;">Client Error: ${error.message}</div>`;
    }
}
