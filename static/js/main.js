// Base URL for API calls
const API_BASE_URL = '/HemolixFusion';
var sourceData = null;
var targetData = null;
var sourcePreviewHTML = null;  // Store preview HTML from backend
var targetPreviewHTML = null;  // Store preview HTML from backend
var pendingMergeConfig = null;  // Store merge configuration for HITL approval workflow

// Update merge value strategy radio button styles (defined early for inline onchange)
function updateMergeStrategyStyles() {
    var radios = document.querySelectorAll('input[name="mergeValueStrategy"]');
    radios.forEach(function (radio) {
        var label = radio.closest('label');
        if (radio.checked) {
            label.style.borderColor = '#667eea';
            label.style.background = '#f0f4ff';
        } else {
            label.style.borderColor = '#e2e8f0';
            label.style.background = 'transparent';
        }
    });
}

// Toggle custom formula input field visibility
function toggleCustomFormulaInput() {
    var customRadio = document.querySelector('input[name="mergeValueStrategy"][value="custom"]');
    var customFormulaContainer = document.getElementById('customFormulaContainer');

    if (customRadio && customFormulaContainer) {
        if (customRadio.checked) {
            customFormulaContainer.style.display = 'block';
        } else {
            customFormulaContainer.style.display = 'none';
        }
    }
}

// Get selected merge value strategy (defined early for use in payload)
function getMergeValueStrategy() {
    var selected = document.querySelector('input[name="mergeValueStrategy"]:checked');
    var value = selected ? selected.value : 'delimited';

    // If custom formula is selected, get the formula text
    if (value === 'custom') {
        var customFormulaInput = document.getElementById('customFormulaInput');
        var customFormula = customFormulaInput ? customFormulaInput.value.trim() : '';
        console.log('[DEBUG] getMergeValueStrategy: custom formula -', customFormula);
        return {
            type: 'custom',
            formula: customFormula
        };
    }

    console.log('[DEBUG] getMergeValueStrategy:', value, 'selected element:', selected);
    return value;
}
// File upload handlers
document.getElementById('sourceFile')?.addEventListener('change', function (e) { handleFileUpload(e, 'source'); });
document.getElementById('targetFile')?.addEventListener('change', function (e) { handleFileUpload(e, 'target'); });
// Text input handlers
document.getElementById('sourceText')?.addEventListener('input', function (e) { handleTextInput(e, 'source'); });
document.getElementById('targetText')?.addEventListener('input', function (e) { handleTextInput(e, 'target'); });
// Data toggle checkbox handlers
var sourceDataToggle = document.getElementById('sourceDataToggle');
if (sourceDataToggle) {
    sourceDataToggle.addEventListener('change', function (e) {
        handleDataToggle(e, 'source');
    });
}
var targetDataToggle = document.getElementById('targetDataToggle');
if (targetDataToggle) {
    targetDataToggle.addEventListener('change', function (e) {
        handleDataToggle(e, 'target');
    });
}
// Set default state - data hidden by default
if (sourceDataToggle) {
    sourceDataToggle.checked = false;
}
if (targetDataToggle) {
    targetDataToggle.checked = false;
}
function toggleTextInput(type) {
    var textarea = document.getElementById(type + 'Text');
    var isVisible = getComputedStyle(textarea).display !== 'none';
    textarea.style.display = isVisible ? 'none' : 'block';
    if (!isVisible) { textarea.focus(); }
}
function handleDataToggle(event, type) {
    console.log('Data toggle changed for', type, 'checked:', event.target.checked);
    // Update existing table cells with data-cell-value attributes in preview
    updateTableDataDisplay(type, event.target.checked);
    // Also update the mapping tables if they exist
    var mappingContainer = type === 'source' ? 'sourceTableDisplay' : 'targetTableDisplay';
    updateTableDataDisplay(mappingContainer, event.target.checked);
    // Also refresh the results table if it exists and has match data
    if (window.lastResult && window.lastResult.data) {
        var resultsContainer = document.getElementById('resultsContainer');
        if (resultsContainer.style.display !== 'none') {
            // Refresh the mapping display - use match_result for merge operations - support both formats
            var hmdMerged = window.lastResult.data.HMD_Merged_Schema || (window.lastResult.data.Merged_Schema && window.lastResult.data.Merged_Schema.HMD_Merged_Schema);
            var vmdMerged = window.lastResult.data.VMD_Merged_Schema || (window.lastResult.data.Merged_Schema && window.lastResult.data.Merged_Schema.VMD_Merged_Schema);
            if (hmdMerged || vmdMerged) {
                // This is a merge operation - use match results for Schema Mapping
                if (window.lastResult.match_result) {
                    displayEnhancedMapping(window.lastResult.match_result);
                } else {
                    displayEnhancedMapping(window.lastResult.data);
                }
            } else {
                // This is a match operation - use main data
                displayEnhancedMapping(window.lastResult.data);
            }
        }
    }
}
function updateTableDataDisplay(type, showData) {
    // Find all table cells with data-cell-value attributes in the specified type
    var container;
    // Handle both preview containers and direct container IDs
    if (type.includes('TableDisplay') || type.includes('Preview')) {
        container = document.getElementById(type);
    } else {
        container = document.getElementById(type + 'Preview') ||
            document.getElementById(type + 'TableDisplay');
    }
    if (!container) return;
    var dataCells = container.querySelectorAll('td[data-cell-value]');
    dataCells.forEach(function (cell) {
        var cellValue = cell.getAttribute('data-cell-value') || '';
        // Don't modify VMD cells (first column)
        if (cell.classList.contains('vmd-cell') || cell.classList.contains('vmd-category')) {
            return;
        }
        if (showData && cellValue) {
            // Check if cell already has colored content from server-side generation
            if (cell.innerHTML && cell.innerHTML.includes('<span style="color:')) {
                // Cell already has colored content from Python, don't override it
                return;
            }
            // Determine table type to apply appropriate color
            var containerId = container.id;
            var color = '#333'; // default color
            // Check if cellValue contains t1|t2 format (merged tables)
            if (cellValue.includes(' | ')) {
                var parts = cellValue.split(' | ');
                var t1Value = parts[0] ? parts[0].trim() : '';
                var t2Value = parts[1] ? parts[1].trim() : '';
                // Apply same color coding as merged tables
                var t1Formatted = t1Value ? '<span style="color: #8B4513; font-weight: bold;">' + t1Value + '</span>' : '-';
                var t2Formatted = t2Value ? '<span style="color: #800080; font-weight: bold;">' + t2Value + '</span>' : '-';
                // Check if this is the main merged schema display
                if (containerId.includes('mainMerged') || containerId.includes('mergedSchema')) {
                    // For main merged table, display with internal dashed separator
                    cell.innerHTML = '<div class="merged-cell-separator" style="position: relative;">' +
                        '<div class="cell-data">' + t1Formatted + '</div>' +
                        '<div class="cell-data">' + t2Formatted + '</div>' +
                        '</div>';
                } else {
                    // For other tables, keep the pipe separator
                    cell.innerHTML = t1Formatted + ' | ' + t2Formatted;
                }
            } else {
                // For source tables (left side) - use brown color for t1 data
                if (containerId.includes('source') || containerId.includes('Source')) {
                    color = '#8B4513'; // brown
                }
                // For target tables (right side) - use purple color for t2 data  
                else if (containerId.includes('target') || containerId.includes('Target')) {
                    color = '#800080'; // purple
                }
                cell.textContent = cellValue;
                cell.style.color = color;
            }
            cell.style.fontWeight = 'bold';
            cell.style.textAlign = 'center';
        } else {
            cell.textContent = '';
            cell.style.color = 'transparent';
            cell.style.fontWeight = 'bold';
        }
    });
    // Apply dashed border styling if this is the main merged schema display
    if (type === 'mainMergedSchemaDisplay') {
        setTimeout(function () {
            addVerticalDashedLines('mainMergedSchemaDisplay');
        }, 50);
    }
}

// Load preloaded JSON pair from server
async function loadPreloadedPair(pairName) {
    if (!pairName) return;

    console.log(`⚡ [PRELOAD] Loading preloaded pair: ${pairName}`);
    showLoading(true);

    try {
        const response = await fetch(API_BASE_URL + '/load-pair/' + pairName);
        const result = await response.json();

        if (!result.success) {
            throw new Error(result.error || 'Failed to load preloaded pair');
        }

        console.log(`✅ [PRELOAD] Loaded pair: ${result.pair_name}`, result.pair_info);

        // Set source data and HTML (using same approach as handleFileUpload)
        sourceData = result.source.data;
        window.sourceData = sourceData;
        sourcePreviewHTML = result.source.html || '<p>Data parsed successfully</p>';

        const sourcePreviewEl = document.getElementById('sourcePreview');
        if (sourcePreviewEl) {
            sourcePreviewEl.innerHTML = sourcePreviewHTML;
        }
        const sourceParsedEl = document.getElementById('sourceParsed');
        if (sourceParsedEl) {
            sourceParsedEl.style.display = 'block';
        }
        // Store profile data if available
        if (result.source.profile) {
            window.storeProfileData('source', result.source.profile);
        }
        // Apply current checkbox state
        setTimeout(function () {
            var checkbox = document.getElementById('sourceDataToggle');
            if (checkbox) updateTableDataDisplay('source', checkbox.checked);
        }, 100);

        // Set target data and HTML
        targetData = result.target.data;
        window.targetData = targetData;
        targetPreviewHTML = result.target.html || '<p>Data parsed successfully</p>';

        const targetPreviewEl = document.getElementById('targetPreview');
        if (targetPreviewEl) {
            targetPreviewEl.innerHTML = targetPreviewHTML;
        }
        const targetParsedEl = document.getElementById('targetParsed');
        if (targetParsedEl) {
            targetParsedEl.style.display = 'block';
        }
        // Store profile data if available
        if (result.target.profile) {
            window.storeProfileData('target', result.target.profile);
        }
        // Apply current checkbox state
        setTimeout(function () {
            var checkbox = document.getElementById('targetDataToggle');
            if (checkbox) updateTableDataDisplay('target', checkbox.checked);
        }, 100);

        // Update controls
        updateControls();

        // Show success message
        showSuccess(`✅ Loaded ${result.pair_info.name} successfully!`);

        // Reset the dropdown
        document.getElementById('preloadedPairSelect').value = '';

    } catch (error) {
        console.error('❌ [PRELOAD] Error loading pair:', error);
        showError(`Failed to load preloaded pair: ${error.message}`);
    } finally {
        showLoading(false);
    }
}

// Generate table preview HTML from JSON data
function generateTablePreviewHTML(data, type) {
    const tableName = type === 'source' ? 'Table1' : 'Table2';
    const hmd = data[`${tableName}.HMD`] || [];
    const vmd = data[`${tableName}.VMD`] || [];
    const tableData = data[`${tableName}.Data`] || [];

    let html = `<div class="preview-table-container">`;
    html += `<table class="preview-table" style="width:100%;border-collapse:collapse;font-size:12px;">`;

    // Build header from HMD
    html += `<thead><tr style="background:#667eea;color:white;">`;
    html += `<th style="padding:8px;border:1px solid #ddd;"></th>`; // Empty corner cell

    // Flatten HMD for headers
    const headers = [];
    hmd.forEach(h => {
        if (h.children && h.children.length > 0) {
            h.children.forEach(c => {
                const childKey = Object.keys(c)[0];
                headers.push(`${h.attribute1 || h.attribute2 || h.attribute3 || ''}.${c[childKey]}`);
            });
        } else {
            const attrKey = Object.keys(h).find(k => k.startsWith('attribute'));
            if (attrKey && h[attrKey]) headers.push(h[attrKey]);
        }
    });

    headers.slice(0, 5).forEach(header => {
        html += `<th style="padding:8px;border:1px solid #ddd;">${header.substring(0, 20)}${header.length > 20 ? '...' : ''}</th>`;
    });
    if (headers.length > 5) {
        html += `<th style="padding:8px;border:1px solid #ddd;">...</th>`;
    }
    html += `</tr></thead>`;

    // Build body from VMD and Data
    html += `<tbody>`;
    const maxRows = Math.min(vmd.length, tableData.length, 5);
    for (let i = 0; i < maxRows; i++) {
        const vmdItem = vmd[i];
        let vmdName = '';
        if (typeof vmdItem === 'string') {
            vmdName = vmdItem;
        } else if (vmdItem && vmdItem.attribute1) {
            vmdName = vmdItem.attribute1;
        } else if (vmdItem && typeof vmdItem === 'object') {
            const keys = Object.keys(vmdItem);
            for (const key of keys) {
                if (typeof vmdItem[key] === 'string' && vmdItem[key].trim()) {
                    vmdName = vmdItem[key];
                    break;
                }
            }
        }

        html += `<tr style="background:${i % 2 === 0 ? '#f8f9fa' : 'white'};">`;
        html += `<td style="padding:6px;border:1px solid #ddd;font-weight:600;color:#333;">${vmdName.substring(0, 25)}${vmdName.length > 25 ? '...' : ''}</td>`;

        const rowData = tableData[i] || [];
        const dataSlice = Array.isArray(rowData) ? rowData.slice(0, 5) : [];
        dataSlice.forEach(cell => {
            const cellStr = String(cell || '');
            html += `<td style="padding:6px;border:1px solid #ddd;">${cellStr.substring(0, 15)}${cellStr.length > 15 ? '...' : ''}</td>`;
        });
        if (Array.isArray(rowData) && rowData.length > 5) {
            html += `<td style="padding:6px;border:1px solid #ddd;">...</td>`;
        }
        html += `</tr>`;
    }

    if (vmd.length > 5 || tableData.length > 5) {
        html += `<tr><td colspan="${Math.min(headers.length, 6) + 1}" style="padding:8px;text-align:center;color:#999;">... ${Math.max(vmd.length, tableData.length) - 5} more rows</td></tr>`;
    }

    html += `</tbody></table>`;
    html += `<div style="margin-top:10px;font-size:11px;color:#666;">📊 ${vmd.length} rows × ${headers.length} columns</div>`;
    html += `</div>`;

    return html;
}

async function handleFileUpload(event, type) {
    var file = event.target.files[0];
    if (!file) return;
    var formData = new FormData();
    formData.append('file', file);
    formData.append('type', type);
    showLoading(true);
    try {
        var response = await fetch(API_BASE_URL + '/upload', { method: 'POST', body: formData });
        var result = await response.json();
        if (result.success) {
            if (type === 'source') {
                sourceData = result.data;
                // Store preview HTML for reuse in mapping display
                sourcePreviewHTML = result.html || '<p>Data parsed successfully</p>';
                // Store profile data if available
                if (result.profile) {
                    window.storeProfileData('source', result.profile);
                }
                var sourcePreviewEl = document.getElementById('sourcePreview');
                console.log('sourcePreviewEl found:', !!sourcePreviewEl);
                if (sourcePreviewEl) {
                    sourcePreviewEl.innerHTML = sourcePreviewHTML;
                }
                var sourceParsedEl = document.getElementById('sourceParsed');
                console.log('sourceParsedEl found:', !!sourceParsedEl);
                if (sourceParsedEl) {
                    sourceParsedEl.style.display = 'block';
                    console.log('Set sourceParsed display to block');
                }
                // Apply current checkbox state to new table
                setTimeout(function () {
                    var checkbox = document.getElementById('sourceDataToggle');
                    if (checkbox) updateTableDataDisplay('source', checkbox.checked);
                }, 100);
            } else {
                targetData = result.data;
                // Store preview HTML for reuse in mapping display
                targetPreviewHTML = result.html || '<p>Data parsed successfully</p>';
                // Store profile data if available
                if (result.profile) {
                    window.storeProfileData('target', result.profile);
                }
                var targetPreviewEl = document.getElementById('targetPreview');
                console.log('targetPreviewEl found:', !!targetPreviewEl);
                if (targetPreviewEl) {
                    targetPreviewEl.innerHTML = targetPreviewHTML;
                }
                var targetParsedEl = document.getElementById('targetParsed');
                console.log('targetParsedEl found:', !!targetParsedEl);
                if (targetParsedEl) {
                    targetParsedEl.style.display = 'block';
                    console.log('Set targetParsed display to block');
                }
                // Apply current checkbox state to new table
                setTimeout(function () {
                    var checkbox = document.getElementById('targetDataToggle');
                    if (checkbox) updateTableDataDisplay('target', checkbox.checked);
                }, 100);
            }
            updateControls();
            showSuccess((type.charAt(0).toUpperCase() + type.slice(1)) + ' file processed successfully!');
        } else {
            showError(result.error || 'Upload failed');
        }
    } catch (error) {
        showError('Upload error: ' + error.message);
    } finally {
        showLoading(false);
    }
}
async function handleTextInput(event, type) {
    var text = event.target.value.trim();
    if (!text) {
        if (type === 'source') {
            sourceData = null;
            document.getElementById('sourceParsed').style.display = 'none';
        } else {
            targetData = null;
            document.getElementById('targetParsed').style.display = 'none';
        }
        updateControls();
        return;
    }
    try {
        var response = await fetch(API_BASE_URL + '/parse-text', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ text: text, type: type })
        });
        var result = await response.json();
        if (result.success) {
            if (type === 'source') {
                sourceData = result.data;
                // Store preview HTML for reuse in mapping display
                sourcePreviewHTML = result.html || '<p>JSON parsed successfully</p>';
                // Store profile data if available
                if (result.profile) {
                    window.storeProfileData('source', result.profile);
                }
                var sourcePreviewEl = document.getElementById('sourcePreview');
                console.log('[JSON] sourcePreviewEl found:', !!sourcePreviewEl);
                if (sourcePreviewEl) {
                    sourcePreviewEl.innerHTML = sourcePreviewHTML;
                }
                var sourceParsedEl = document.getElementById('sourceParsed');
                console.log('[JSON] sourceParsedEl found:', !!sourceParsedEl);
                if (sourceParsedEl) {
                    sourceParsedEl.style.display = 'block';
                    console.log('[JSON] Set sourceParsed display to block');
                }
                // Apply current checkbox state to new table
                setTimeout(function () {
                    var checkbox = document.getElementById('sourceDataToggle');
                    if (checkbox) updateTableDataDisplay('source', checkbox.checked);
                }, 100);
            } else {
                targetData = result.data;
                // Store preview HTML for reuse in mapping display
                targetPreviewHTML = result.html || '<p>JSON parsed successfully</p>';
                // Store profile data if available
                if (result.profile) {
                    window.storeProfileData('target', result.profile);
                }
                var targetPreviewEl = document.getElementById('targetPreview');
                console.log('[JSON] targetPreviewEl found:', !!targetPreviewEl);
                if (targetPreviewEl) {
                    targetPreviewEl.innerHTML = targetPreviewHTML;
                }
                var targetParsedEl = document.getElementById('targetParsed');
                console.log('[JSON] targetParsedEl found:', !!targetParsedEl);
                if (targetParsedEl) {
                    targetParsedEl.style.display = 'block';
                    console.log('[JSON] Set targetParsed display to block');
                }
                // Apply current checkbox state to new table
                setTimeout(function () {
                    var checkbox = document.getElementById('targetDataToggle');
                    if (checkbox) updateTableDataDisplay('target', checkbox.checked);
                }, 100);
            }
            updateControls();
        } else {
            showError(result.error || 'Parsing failed');
        }
    } catch (error) {
        showError('Parsing error: ' + error.message);
    }
}
// Toggle merge step visibility
function toggleMergeStep() {
    var mergeContainer = document.getElementById('mergeStepContainer');
    var addButton = document.getElementById('addMergeStep');
    var isVisible = mergeContainer.style.display !== 'none';
    if (isVisible) {
        // Hide merge step
        mergeContainer.style.display = 'none';
        addButton.innerHTML = '+ Add Schema Merge Step';
        addButton.style.background = 'rgba(255,255,255,0.2)';
        addButton.style.borderColor = 'rgba(255,255,255,0.3)';
        // Clear merge selection
        document.getElementById('mergeOperation').value = '';
        document.getElementById('mergeMethod').value = '';
        document.getElementById('mergeLLM').value = '';
    } else {
        // Show merge step
        mergeContainer.style.display = 'block';
        addButton.innerHTML = '✔ Merge Step Added';
        addButton.style.background = 'rgba(34, 197, 94, 0.2)';
        addButton.style.borderColor = 'rgba(34, 197, 94, 0.4)';
    }
    updatePipelineVisualization();
    updateControls();
}
// Update merge method options based on selected operation
function updateMergeMethodOptions() {
    var mergeOperation = document.getElementById('mergeOperation').value;
    var mergeMethodSelect = document.getElementById('mergeMethod');
    // Clear existing options
    mergeMethodSelect.innerHTML = '<option value="">Choose method...</option>';
    if (mergeOperation === 'merge') {
        // Schema Merge methods: Only JSON and Multi-step
        mergeMethodSelect.innerHTML += '<option value="json_default">🏠 JSON (Default)</option>';
        mergeMethodSelect.innerHTML += '<option value="multi_step">🔄 Multi-Step</option>';
    } else if (mergeOperation === 'instance_merge') {
        // Instance Merge methods: JSON and Table partition options
        mergeMethodSelect.innerHTML += '<option value="json_default">🏠 JSON (Default)</option>';
        // mergeMethodSelect.innerHTML += '<option value="table_partition_horizontal">↔️ Table partition</option>';
        // mergeMethodSelect.innerHTML += '<option value="table_partition_vertical">↕️ Table partition (Vertical)</option>';
    } else if (mergeOperation === 'baseline') {
        // Baseline Merge methods: Only JSON
        mergeMethodSelect.innerHTML += '<option value="json_default">🏠 JSON (Default)</option>';
    }
}
function updateMatchingMethodOptions() {
    var matchOperation = document.getElementById('matchOperation').value;
    var matchingMethodSelect = document.getElementById('schemaMatchingType');
    // Clear existing options
    matchingMethodSelect.innerHTML = '<option value="">Choose method...</option>';
    if (matchOperation === 'baseline') {
        // Baseline operation: Only JSON
        matchingMethodSelect.innerHTML += '<option value="json_default">🏠 JSON (Default)</option>';
    } else if (matchOperation === 'operator') {
        // Operator operation: JSON, KG, Multi-step
        matchingMethodSelect.innerHTML += '<option value="json_default">🏠 JSON (Default)</option>';
        matchingMethodSelect.innerHTML += '<option value="kg_enhanced">🧠 Knowledge Graph Enhanced</option>';
        matchingMethodSelect.innerHTML += '<option value="multi_step">🔄 Multi-Step Analysis</option>';
    }
}

// Helper functions for pipeline visualization
function getMatchingIcon(type) {
    const icons = {
        'json_default': '🏠',
        'kg_enhanced': '🧠',
        'baseline': '📊',
        'multi_step': '🔄'
    };
    return icons[type] || '📂';
}
function getMatchingName(type) {
    const names = {
        'json_default': 'JSON Match',
        'kg_enhanced': 'KG Match',
        'baseline': 'Baseline Match',
        'multi_step': 'Multi-Step Match'
    };
    return names[type] || 'Schema Match';
}
function getMatchingDesc(type) {
    const descs = {
        'json_default': 'Schema Matches',
        'kg_enhanced': 'Enhanced Matching',
        'baseline': 'Basic Matching',
        'multi_step': 'Advanced Analysis'
    };
    return descs[type] || 'Schema Analysis';
}
function getMergeIcon(method) {
    const icons = {
        'json_default': '🏠',
        'baseline': '📊',
        'kg_enhanced': '🧠',
        'multi_step': '🔄',
        'loss_less': '📊'
    };
    return icons[method] || '📂—';
}
function getMergeName(operation, method) {
    const operationNames = {
        'merge': 'Schema Merge',
        'instance_merge': 'Instance Merge',
        'baseline': 'Baseline Merge'
    };
    const methodNames = {
        'json_default': 'JSON',
        'kg_enhanced': 'KG',
        'multi_step': 'Multi-Step'
    };
    return `${methodNames[method] || ''} ${operationNames[operation] || 'Merge'}`;
}
function getMergeDesc(operation) {
    const descs = {
        'merge': 'Unified Schema',
        'instance_merge': 'Instance Data',
        'baseline': 'Basic Merge'
    };
    return descs[operation] || 'Combined Data';
}
// Pipeline visualization function
function updatePipelineVisualization() {
    var matchOperation = document.getElementById('matchOperation').value;
    var matchingType = document.getElementById('schemaMatchingType').value;
    var mergeOperation = document.getElementById('mergeOperation').value;
    var mergeMethod = document.getElementById('mergeMethod').value;
    var matchingLLM = document.getElementById('matchingLLM').value;
    var mergeLLM = document.getElementById('mergeLLM').value;
    var visualization = document.getElementById('pipelineVisualization');
    var mergeContainer = document.getElementById('mergeStepContainer');
    var isMergeVisible = document.getElementById('mergeOperation') && document.getElementById('mergeOperation').value !== '';
    if (!matchOperation || !matchingType) {
        visualization.innerHTML = `<div style="text-align: center; color: #718096; font-style: italic; padding: 20px;">
        <span style="font-size: 24px; display: block; margin-bottom: 8px;">📂®</span>
        Choose a matching method to see your pipeline
    </div>`;
        return;
    }
    var steps = [];
    // Add input step
    steps.push({
        name: 'Input Tables',
        type: 'input',
        icon: '📄',
        description: 'Schema Documents'
    });
    // Add matching step
    var matchingNames = {
        'json_default': 'JSON Match',
        'kg_enhanced': 'KG Match',
        'baseline': 'Baseline Match',
        'multi_step': 'Multi-Step Match'
    };
    var matchingIcons = {
        'json_default': '🏠',
        'kg_enhanced': '🧠',
        'baseline': '📊',
        'multi_step': '🔄'
    };
    var llmToUse = matchingLLM || 'Auto-select';
    var llmDisplay = (llmToUse && llmToUse.includes && llmToUse.includes('claude')) ? '🤖 Claude' :
        (llmToUse && llmToUse.includes && llmToUse.includes('llama')) ? '🦙 Llama' :
            (llmToUse && llmToUse.includes && llmToUse.includes('gemini')) ? '💎 Gemini' :
                (llmToUse && llmToUse.includes && llmToUse.includes('qwen')) ? '📂 Qwen' :
                    (llmToUse && llmToUse.includes && llmToUse.includes('gpt')) ? '🧠 GPT' :
                        (llmToUse && llmToUse.includes && llmToUse.includes('deepseek')) ? '📂 DeepSeek' : '🤖 Auto';
    steps.push({
        name: matchingNames[matchingType] || matchingType,
        type: 'matching',
        icon: matchingIcons[matchingType] || '🧩',
        llm: llmDisplay,
        variable: 'Schema Matches'
    });
    // Add merge step if visible and selected
    if (isMergeVisible && mergeOperation && mergeMethod) {
        var mergeNames = {
            'json_default': 'JSON Merge',
            'kg_enhanced': 'KG Merge',
            'multi_step': 'Multi-Step Merge',
            'loss_less': 'Loss-Less Merge',
            'table_partition_horizontal': 'Merge<br>+ Table Partition',
            'table_partition_vertical': 'Merge<br>+ Table Partition'
        };
        var mergeIcons = {
            'json_default': '🏠',
            'kg_enhanced': '🧠',
            'multi_step': '🔄',
            'loss_less': '📊'
        };
        var mergeLLMToUse = mergeLLM || 'Auto-select';
        var mergeLLMDisplay = (mergeLLMToUse && mergeLLMToUse.includes && mergeLLMToUse.includes('claude')) ? '🤖 Claude' :
            (mergeLLMToUse && mergeLLMToUse.includes && mergeLLMToUse.includes('llama')) ? '🦙 Llama' :
                (mergeLLMToUse && mergeLLMToUse.includes && mergeLLMToUse.includes('gemini')) ? '💎 Gemini' :
                    (mergeLLMToUse && mergeLLMToUse.includes && mergeLLMToUse.includes('qwen')) ? '📂 Qwen' :
                        (mergeLLMToUse && mergeLLMToUse.includes && mergeLLMToUse.includes('gpt')) ? '🧠 GPT' :
                            (mergeLLMToUse && mergeLLMToUse.includes && mergeLLMToUse.includes('deepseek')) ? '📂 DeepSeek' : '🤖 Auto';
        var operationPrefix = mergeOperation === 'instance_merge' ? 'Instance ' : '';
        steps.push({
            name: operationPrefix + (mergeNames[mergeMethod] || mergeMethod),
            type: 'merge',
            icon: mergeIcons[mergeMethod] || '📂',
            llm: mergeLLMDisplay,
            variable: mergeOperation === 'instance_merge' ? 'Instance Data' : 'Unified Schema'
        });
    }
    // Add output step
    var outputName = isMergeVisible && mergeOperation && mergeMethod ? 'Merged JSON' : 'Match Results';
    steps.push({
        name: outputName,
        type: 'output',
        icon: '📤',
        description: 'Final Output'
    });
    // Generate modern visualization HTML
    var html = '<div style="display: flex; align-items: center; justify-content: center; flex-wrap: wrap; gap: 12px; padding: 8px;">';
    steps.forEach((step, index) => {
        // Add animated arrow between steps
        if (index > 0) {
            html += `<div style="display: flex; align-items: center;">
            <div style="width: 0; height: 0; border-left: 8px solid #cbd5e0; border-top: 6px solid transparent; border-bottom: 6px solid transparent; margin: 0 4px;"></div>
        </div>`;
        }
        // Step card with modern styling
        var cardStyle = '';
        if (step.type === 'input' || step.type === 'output') {
            cardStyle = 'background: linear-gradient(135deg, #f7fafc 0%, #edf2f7 100%); border: 2px solid #e2e8f0;';
        } else if (step.type === 'matching') {
            cardStyle = 'background: linear-gradient(135deg, #f0fff4 0%, #e6fffa 100%); border: 2px solid #38b2ac;';
        } else if (step.type === 'merge') {
            cardStyle = 'background: linear-gradient(135deg, #fffaf0 0%, #fef5e7 100%); border: 2px solid #ed8936;';
        }
        html += `<div style="${cardStyle} border-radius: 12px; padding: 12px 16px; text-align: center; min-width: 120px; box-shadow: 0 2px 8px rgba(0,0,0,0.1); transition: transform 0.2s;">`;
        if (step.icon) {
            html += `<div style="font-size: 20px; margin-bottom: 4px;">${step.icon}</div>`;
        }
        html += `<div style="font-weight: 600; font-size: 13px; color: #2d3748; margin-bottom: 2px;">${step.name}</div>`;
        if (step.llm) {
            html += `<div style="font-size: 12px; color: #4a5568; background: rgba(255,255,255,0.8); border-radius: 10px; padding: 2px 6px; margin: 2px 0;">${step.llm}</div>`;
        }
        // Add partition size input for partition merge steps
        if (step.type === 'merge' && step.name.toLowerCase().includes('partition')) {
            html += `<div style="margin-top: 6px; padding-top: 6px; border-top: 1px dashed #ed8936;">
                <div style="display: flex; align-items: center; justify-content: center; gap: 10px;">
                    <div style="text-align: center;">
                        <label style="font-size: 13px; color: #744210; display: block; margin-bottom: 3px;">Rows-per-partition</label>
                        <input type="number" id="partitionSizeInput" value="8" min="1" max="100" 
                            style="width: 50px; padding: 4px 6px; border: 1px solid #ed8936; border-radius: 4px; font-size: 13px; text-align: center;"
                            onclick="event.stopPropagation();"
                            onchange="updateTotalPartitionsDisplay();"
                            oninput="updateTotalPartitionsDisplay();"
                            title="Number of rows per partition">
                    </div>
                    <div style="color: #ed8936; font-size: 16px; font-weight: bold;">→</div>
                    <div style="text-align: center;">
                        <label style="font-size: 13px; color: #744210; display: block; margin-bottom: 3px;">Total Partitions</label>
                        <div id="totalPartitionsDisplay" style="width: 50px; padding: 4px 6px; border: 1px solid #9C27B0; border-radius: 4px; font-size: 13px; text-align: center; background: #f3e5f5; color: #9C27B0; font-weight: 600;">-</div>
                    </div>
                </div>
            </div>`;
        }
        if (step.variable) {
            html += `<div style="font-size: 9px; color: #2b6cb0; font-style: italic; margin-top: 2px;">→ ${step.variable}</div>`;
        }
        html += '</div>';
    });
    html += '</div>';
    // Estimation metrics removed as requested
    visualization.innerHTML = html;

    // Update total partitions display after rendering
    updateTotalPartitionsDisplay();
}

// Update the Total Partitions display based on source data and rows-per-partition input
function updateTotalPartitionsDisplay() {
    const display = document.getElementById('totalPartitionsDisplay');
    const input = document.getElementById('partitionSizeInput');
    if (!display || !input) return;

    // Get rows-per-partition value
    const rowsPerPartition = parseInt(input.value) || 8;

    // Get source data row count using the same function used for partition stats
    if (typeof sourceData !== 'undefined' && sourceData) {
        const totalRows = countDataRowsFromSchema(sourceData);
        if (totalRows > 0) {
            const totalPartitions = Math.ceil(totalRows / rowsPerPartition);
            display.textContent = totalPartitions;
        } else {
            display.textContent = '-';
        }
    } else {
        display.textContent = '-';
    }
}

// Parameter control functions
function updateControls() {
    var matchOperation = document.getElementById('matchOperation').value;
    var schemaMatchingType = document.getElementById('schemaMatchingType').value;
    var mergeOperation = document.getElementById('mergeOperation').value;
    var mergeMethod = document.getElementById('mergeMethod').value;
    var processBtn = document.getElementById('processBtn');
    var schemaTypeInfo = document.getElementById('schemaTypeInfo');
    var schemaTypeText = document.getElementById('schemaTypeText');
    var mergeContainer = document.getElementById('mergeStepContainer');
    var isMergeVisible = document.getElementById('mergeOperation') && document.getElementById('mergeOperation').value !== '';
    // Update pipeline visualization when controls change
    updatePipelineVisualization();
    // Can process if we have data and match operation and matching method, and if merge is visible then both merge operation and method
    var canProcess = sourceData && targetData && matchOperation && schemaMatchingType && (!isMergeVisible || (mergeOperation && mergeMethod));
    // console.log('[DEBUG] Button visibility check:', {
    //     sourceData: !!sourceData,
    //     targetData: !!targetData,
    //     matchOperation: matchOperation,
    //     schemaMatchingType: schemaMatchingType,
    //     isMergeVisible: isMergeVisible,
    //     mergeOperation: mergeOperation,
    //     mergeMethod: mergeMethod,
    //     canProcess: canProcess
    // });
    // Show/hide advanced parameters based on selected LLMs
    var matchingLLM = document.getElementById('matchingLLM').value;
    var mergeLLM = document.getElementById('mergeLLM').value;
    var advancedElements = document.querySelectorAll('.groq-only');

    // Show for models that typically support these parameters (OpenAI-compatible APIs)
    var isAdvancedModel = (matchingLLM && (matchingLLM.includes('llama') || matchingLLM.includes('gpt') ||
        matchingLLM.includes('qwen') || matchingLLM.includes('deepseek'))) ||
        (mergeLLM && (mergeLLM.includes('llama') || mergeLLM.includes('gpt') ||
            mergeLLM.includes('qwen') || mergeLLM.includes('deepseek')));

    advancedElements.forEach(element => {
        if (isAdvancedModel) {
            element.style.display = 'grid';
            element.classList.add('visible');
        } else {
            element.style.display = 'none';
            element.classList.remove('visible');
        }
    });
    // Show schema type info when both files are uploaded
    if (sourceData && targetData) {
        // Auto-detect schema complexity
        var sourceComplexity = detectSchemaComplexity(sourceData);
        var targetComplexity = detectSchemaComplexity(targetData);
        var detectedSchemaType = (sourceComplexity === 'complex' || targetComplexity === 'complex') ? 'complex' : 'relational';
        schemaTypeInfo.style.display = 'block';
        schemaTypeText.textContent = (detectedSchemaType === 'complex' ? 'Complex (HMD/VMD)' : 'Relational');
        // Store globally for other functions to use
        window.schemaType = detectedSchemaType;
    } else {
        schemaTypeInfo.style.display = 'none';
        window.schemaType = null;
    }
    // Show process button when all requirements are met
    if (canProcess) {
        processBtn.style.display = 'inline-block';
        processBtn.disabled = false;
        // Update button text based on operation type
        if (isMergeVisible && mergeOperation) {
            if (mergeOperation === 'instance_merge') {
                processBtn.textContent = 'Run Instance Merge Pipeline';
            } else if (mergeOperation === 'baseline') {
                processBtn.textContent = 'Run Baseline Merge Pipeline';
            } else {
                processBtn.textContent = 'Run Schema Fusion Pipeline';
            }
        } else {
            processBtn.textContent = 'Run Schema Matching';
        }
    } else {
        processBtn.style.display = 'none';
        processBtn.disabled = true;
    }

    // Fetch and display performance metrics
    fetchPipelineMetrics();
}
// Default parameters - no longer configurable via UI
function getParameterValues() {
    return {
        temperature: 0.1,
        max_tokens: 2000,
        top_p: 0.85,
        frequency_penalty: 0.0,
        presence_penalty: 0.0
    };
}
function showPipelineOptions() {
    var pipelineSelection = document.getElementById('pipelineSelection');
    var pipelineOptions = document.getElementById('pipelineOptions');
    var processingType = document.getElementById('processingType').value;
    if (!sourceData || !targetData) return;
    // Use the globally stored schema type (already detected in updateControls)
    var schemaType = window.schemaType;
    var pipelines = [];
    if (processingType === 'baseline') {
        pipelines = [
            {
                id: 'baseline_match',
                title: 'Baseline Schema Match',
                description: 'BSM',
                operation: 'match'
            },
            {
                id: 'baseline_match_merge',
                title: 'Baseline Schema Match → Merge',
                description: 'BSM → BME',
                operation: 'merge'
            }
        ];
    } else if (processingType === 'operator') {
        pipelines = [
            {
                id: 'operator_match',
                title: 'Operator Schema Match',
                description: '<b>SM<sub>JSON</sub></b>',
                operation: 'match'
            },
            {
                id: 'kg_operator_match',
                title: 'KG-Enhanced Operator Schema Match',
                description: '<b>KG-SM<sub>JSON</sub></b>',
                operation: 'match'
            },
            {
                id: 'operator_match_merge',
                title: 'Operator Schema Match → Merge',
                description: '<b>SM<sub>JSON</sub> → SME</b>',
                operation: 'merge'
            },
            {
                id: 'operator_match_instance_merge',
                title: 'Operator Schema Match → Instance Merge',
                description: '<b>SM<sub>JSON</sub> → IME<sub>LL</sub></b>',
                operation: 'instance_merge'
            }
        ];
    } else if (processingType === 'multi_step') {
        pipelines = [
            {
                id: 'multi_step_match',
                title: 'Multi-Step Schema Match',
                description: '<b>3×SM + Ensemble</b>',
                operation: 'match'
            },
            {
                id: 'multi_step_merge',
                title: 'Multi-Step Schema Match → Merge',
                description: '<b>3×SM + Ensemble → SME</b>',
                operation: 'merge'
            },
            {
                id: 'multi_step_instance_merge',
                title: 'Multi-Step Schema Match → Instance Merge',
                description: '<b>3×SM + Ensemble → IME</b>',
                operation: 'instance_merge'
            }
        ];
    }
    // Clear previous options
    pipelineOptions.innerHTML = '';
    // Add pipeline options (schema type info is now shown above the dropdown)
    pipelines.forEach(function (pipeline) {
        var option = document.createElement('div');
        option.className = 'pipeline-option';
        option.setAttribute('data-pipeline', pipeline.id);
        option.setAttribute('data-operation', pipeline.operation);
        option.innerHTML = `
        <h5>${pipeline.title}</h5>
        <p>${pipeline.description}</p>
    `;
        option.addEventListener('click', function () {
            // Remove previous selection
            document.querySelectorAll('.pipeline-option').forEach(opt => opt.classList.remove('selected'));
            // Select this option
            this.classList.add('selected');
            // Show and update process button
            var processBtn = document.getElementById('processBtn');
            processBtn.style.display = 'inline-block';
            processBtn.textContent = 'Run Selected Plan';
            // Store selected pipeline
            window.selectedPipeline = pipeline;
        });
        pipelineOptions.appendChild(option);
    });
    pipelineSelection.style.display = 'block';
}
function hidePipelineOptions() {
    var pipelineSelection = document.getElementById('pipelineSelection');
    var processBtn = document.getElementById('processBtn');
    pipelineSelection.style.display = 'none';
    processBtn.style.display = 'none';
    window.selectedPipeline = null;
}
function detectSchemaComplexity(schemaData) {
    if (!schemaData || typeof schemaData !== 'object') {
        return 'relational';
    }
    // Check for complex schema indicators
    for (var key in schemaData) {
        if (key.endsWith('.HMD') || key.endsWith('.VMD')) {
            var value = schemaData[key];
            if (Array.isArray(value) && value.length > 0) {
                // Check if any item has children
                for (var i = 0; i < value.length; i++) {
                    var item = value[i];
                    if (item && typeof item === 'object' && item.children) {
                        return 'complex';
                    }
                    // Check for nested structure in attribute names
                    if (item && typeof item === 'object') {
                        for (var attrKey in item) {
                            var attrValue = item[attrKey];
                            if (typeof attrValue === 'string' && attrValue.includes('.')) {
                                return 'complex';
                            }
                        }
                    }
                }
            }
        }
    }
    // Check for hierarchical structure in attribute names
    for (var key in schemaData) {
        var value = schemaData[key];
        if (Array.isArray(value)) {
            for (var i = 0; i < value.length; i++) {
                var item = value[i];
                if (typeof item === 'string' && item.includes('.')) {
                    return 'complex';
                } else if (item && typeof item === 'object') {
                    for (var attrKey in item) {
                        var attrValue = item[attrKey];
                        if (typeof attrValue === 'string' && attrValue.includes('.')) {
                            return 'complex';
                        }
                    }
                }
            }
        }
    }
    return 'relational';
}
// Control handlers
// Note: onchange events are handled inline for the new pipeline elements
document.getElementById('processBtn')?.addEventListener('click', async function () {
    if (!sourceData || !targetData) return;
    var matchOperation = document.getElementById('matchOperation').value;
    var schemaMatchingType = document.getElementById('schemaMatchingType').value;
    var mergeOperation = document.getElementById('mergeOperation').value;
    var mergeMethod = document.getElementById('mergeMethod').value;
    var mergeContainer = document.getElementById('mergeStepContainer');
    var isMergeVisible = document.getElementById('mergeOperation') && document.getElementById('mergeOperation').value !== '';
    if (!matchOperation) {
        showError('Please select a match operation');
        return;
    }
    if (!schemaMatchingType) {
        showError('Please select a schema matching method');
        return;
    }
    if (isMergeVisible && (!mergeOperation || !mergeMethod)) {
        showError('Please select both merge operation and method, or remove the merge step');
        return;
    }
    // Auto-detect schema complexity
    var sourceComplexity = detectSchemaComplexity(sourceData);
    var targetComplexity = detectSchemaComplexity(targetData);
    var schemaType = (sourceComplexity === 'complex' || targetComplexity === 'complex') ? 'complex' : 'relational';
    // Get LLM selections for each step (default to first available if not selected)
    var matchingLLM = document.getElementById('matchingLLM').value || 'claude-3-5-haiku-20241022';
    var mergeLLM = isMergeVisible ? (document.getElementById('mergeLLM').value || 'claude-3-5-haiku-20241022') : '';
    // Map flexible UI choices to working backend format
    var processingType, operationType;
    // Map match operation and matching method to processing type
    if (matchOperation === 'baseline') {
        processingType = 'baseline';  // Always baseline for baseline operation
    } else if (matchOperation === 'operator') {
        if (schemaMatchingType === 'multi_step') {
            processingType = 'multi_step';  // Multi-step processing
        } else {
            processingType = 'operator';  // JSON or KG use operator processing
        }
    }
    // HITL: Store merge configuration if merge is requested, but do MATCH FIRST
    // Applies to ALL merge operations (JSON-based AND partition-based)
    var isPartitionMerge = mergeMethod && (mergeMethod.includes('partition') || mergeMethod.includes('horizontal_partition') || mergeMethod.includes('vertical_partition'));

    if (isMergeVisible && mergeOperation) {
        // Save merge config for later (after user approves matches)
        // This applies to: ALL merge operations (JSON and Partition-based)
        // IMPORTANT: Use the global override if this is an automated run, 
        // because the DOM might have been clobbered during UI updates
        const finalMergeOp = window._automatedMergeOp || mergeOperation;
        if (window._automatedMergeOp) {
            console.log(`🔒 [HITL-STORE] Using automated override for pending config: "${finalMergeOp}"`);
            // DO NOT clear window._automatedMergeOp here, buildMergePayload needs it too
        }

        pendingMergeConfig = {
            mergeOperation: finalMergeOp,
            mergeMethod: mergeMethod,
            mergeLLM: mergeLLM,
            mergeValueStrategy: getMergeValueStrategy(),
            processingType: finalMergeOp === 'baseline' ? 'baseline' : processingType,
            matchOperation: matchOperation,
            schemaMatchingType: schemaMatchingType,
            matchingLLM: matchingLLM,
            isPartitionMerge: isPartitionMerge,
            partitionPhase: isPartitionMerge ? 'match' : null  // Track partition workflow phase
        };

        if (isPartitionMerge) {
            console.log('📋 [HITL-PARTITION] Phase 1: Will do MATCH first, then wait for approval');
        } else {
            console.log('📋 [HITL] JSON-based merge requested - will do MATCH first, then wait for approval');
        }

        // Force match-only operation for now
        operationType = 'match';
    } else {
        // Match-only operation
        operationType = 'match';
        pendingMergeConfig = null;  // Clear any pending merge
    }
    var payload = {
        sourceSchema: JSON.stringify(sourceData),
        targetSchema: JSON.stringify(targetData),
        schemaType: schemaType,
        processingType: processingType,
        operationType: operationType,
        llmModel: matchingLLM || 'claude-3-5-haiku-20241022',  // Use selected LLM
        parameters: getParameterValues(),
        // Flag to indicate if merge step should use multi-step processing
        useMergeMultiStep: isMergeVisible && mergeMethod === 'multi_step',
        // Keep flexible info for metrics display
        flexibleConfig: {
            matchOperation: matchOperation,
            schemaMatchingType: schemaMatchingType,
            mergeOperation: mergeOperation,
            mergeMethod: mergeMethod,
            matchingLLM: matchingLLM,
            mergeLLM: mergeLLM,
            isMergeVisible: isMergeVisible,
            mergeValueStrategy: getMergeValueStrategy()
        }
    };
    showLoading(true);
    hideMessages();
    try {
        // Add API keys to payload if available
        var apiKeys = getApiKeysForRequest();
        if (Object.keys(apiKeys).length > 0) {
            payload.apiKeys = apiKeys;
        }
        var response = await fetch(API_BASE_URL + '/process', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        var result = await response.json();
        // console.log('📂 Server response received:', result);
        // console.log('📂 Response success status:', result.success);
        if (result.success) {
            // console.log('📂 Calling showResults with:', result);
            showResults(result);
            showSuccess('Pipeline executed successfully!');
        } else {
            console.log('âŒ Server returned error:', result.error);
            showError(result.error);
        }
    } catch (error) {
        showError('Processing error: ' + error.message);
    } finally {
        showLoading(false);
    }
});
// Tabs - with debugging
console.log('📂§ Setting up tab click listeners...');
var tabs = document.querySelectorAll('.tab');
console.log('📂§ Found tabs:', tabs.length);
Array.prototype.forEach.call(tabs, function (tab, index) {
    console.log('📂§ Setting up listener for tab', index, ':', tab.getAttribute('data-tab'));
    tab.addEventListener('click', function (e) {
        var tabName = e.currentTarget.getAttribute('data-tab');
        console.log('📂§ TAB CLICKED:', tabName);
        // Simple direct tab switching without function call
        console.log('📂§ Direct tab switch starting...');
        // Remove active from all tabs
        var allTabs = document.querySelectorAll('.tab');
        var allContent = document.querySelectorAll('.tab-content');
        for (var i = 0; i < allTabs.length; i++) {
            allTabs[i].classList.remove('active');
        }
        for (var i = 0; i < allContent.length; i++) {
            allContent[i].classList.remove('active');
        }
        // Add active to clicked tab
        document.getElementById(tabName + '-tab').classList.add('active');
        e.currentTarget.classList.add('active');
        console.log('📂§ Direct tab switch completed for:', tabName);
        // Draw connection lines for mapping tabs
        if (tabName === 'merged-target' || tabName === 'merged-source') {
            console.log('🔄 Drawing lines for mapping tab:', tabName);
            setTimeout(function () {
                var container = document.querySelector('#' + tabName + '-tab .mapping-tables-container');
                if (container && container.querySelector('.mapping-container')) {
                    console.log('🔄 Calling line drawing for:', tabName);
                    drawComplexMappingLinesSimple(container);
                }
            }, 100);
        }
    });
});
function switchTab(tabName) {
    console.log('📂§ SWITCH TAB CALLED:', tabName);
    try {
        // Remove active class from all tabs and content
        var allTabs = document.querySelectorAll('.tab');
        var allContent = document.querySelectorAll('.tab-content');
        for (var i = 0; i < allTabs.length; i++) {
            allTabs[i].classList.remove('active');
        }
        for (var i = 0; i < allContent.length; i++) {
            allContent[i].classList.remove('active');
        }
        // Add active class to selected tab and content
        var tabElement = document.getElementById(tabName + '-tab');
        var tabButton = document.querySelector('[data-tab="' + tabName + '"]');
        if (tabElement) {
            tabElement.classList.add('active');
            console.log('📂§ Tab content activated:', tabName);
        } else {
            console.error('📂§ Tab content not found:', tabName + '-tab');
        }
        if (tabButton) {
            tabButton.classList.add('active');
            console.log('📂§ Tab button activated:', tabName);
        } else {
            console.error('📂§ Tab button not found for:', tabName);
        }
        console.log('📂§ Tab switched to:', tabName);
        // Draw connection lines when switching to mapping tabs  
        if (tabName === 'merged-target' || tabName === 'merged-source') {
            console.log('🔄 User switched to', tabName, '- drawing connection lines immediately');
            setTimeout(function () {
                var mappingTablesContainer = document.querySelector('#' + tabName + '-tab .mapping-tables-container');
                console.log('📂 Tab switch - Container found:', !!mappingTablesContainer);
                if (mappingTablesContainer) {
                    var mappingContainer = mappingTablesContainer.querySelector('.mapping-container');
                    console.log('📂 Tab switch - Mapping container found:', !!mappingContainer);
                    if (mappingContainer) {
                        console.log('🔄 Tab switch - Drawing lines for', tabName);
                        drawComplexMappingLinesSimple(mappingTablesContainer);
                    } else {
                        console.log('âŒ Tab switch - No mapping container found in', tabName);
                    }
                } else {
                    console.log('âŒ Tab switch - No mapping tables container found for', tabName);
                }
            }, 100);
        }
    } catch (error) {
        console.error('📂§ ERROR in switchTab execution:', error);
    }
}
function showResults(result) {
    // Clear stale data and set fresh data immediately
    var mainMergedContainer = document.getElementById('mainMergedSchemaDisplay');
    if (mainMergedContainer) {
        mainMergedContainer.innerHTML = '';
        console.log('🔄 Cleared main merged table at start of showResults');
    }
    // Set fresh result data immediately
    window.lastResult = result;
    document.getElementById('jsonOutput').value = JSON.stringify(result.data, null, 2);

    // Display partition stats if available
    if (result.partition_stats) {
        displayPartitionStats(result.partition_stats);
    } else {
        // Hide partition stats section if not available
        hidePartitionStats();
    }
    // Check if this is a merge operation
    // Support both old and new JSON structure formats
    var hmdMerged = result.data.HMD_Merged_Schema || (result.data.Merged_Schema && result.data.Merged_Schema.HMD_Merged_Schema);
    var vmdMerged = result.data.VMD_Merged_Schema || (result.data.Merged_Schema && result.data.Merged_Schema.VMD_Merged_Schema);
    console.log('📂 Checking merge operation condition:', {
        'HMD_Merged_Schema': hmdMerged,
        'VMD_Merged_Schema': vmdMerged,
        'condition_result': !!(hmdMerged || vmdMerged)
    });
    if (hmdMerged || vmdMerged) {
        // This is a merge operation - show merge tabs
        // document.querySelector('[data-tab="merged-source"]').style.display = 'block';
        // document.querySelector('[data-tab="merged-target"]').style.display = 'block';

        // HITL: For partition workflows, show approval button after schema merge
        const approvalContainer = document.getElementById('proceedToMergeContainer');
        if (pendingMergeConfig && pendingMergeConfig.isPartitionMerge &&
            (pendingMergeConfig.partitionPhase === 'schema_merge' || pendingMergeConfig.partitionPhase === 'partitions_created')) {

            approvalContainer.style.display = 'block';

            // Update button text based on current phase
            const approvalTitle = approvalContainer.querySelector('h3');
            const approvalDesc = approvalContainer.querySelector('p');
            const approvalButton = approvalContainer.querySelector('button');

            if (pendingMergeConfig.partitionPhase === 'schema_merge') {
                console.log('📋 [HITL-PARTITION] Phase 2 complete - showing approval button for Phase 3');
                approvalTitle.textContent = '📋 Phase 2: Schema Merge Complete';
                approvalDesc.textContent = 'Review the merged schema above. Edit it in the Raw Results tab if needed, then proceed to Phase 3 (Create Partitions).';
                approvalButton.innerHTML = '✓ Approve & Create Partitions';
            } else if (pendingMergeConfig.partitionPhase === 'partitions_created') {
                console.log('📋 [HITL-PARTITION] Phase 2 complete (Phase 3 skipped) - showing approval button for Phase 4');
                approvalTitle.textContent = '📋 Phase 2: Schema Merge Complete';
                approvalDesc.textContent = 'Review the merged schema above. Partitions are ready. Click to proceed to Phase 4 (Merge Partitions).';
                approvalButton.innerHTML = '✓ Approve & Merge Partitions';
            }
        } else {
            // For regular merge operations, hide the approval button
            approvalContainer.style.display = 'none';
        }


        // For merge operations, use the match_result for Schema Mapping tab
        if (result.match_result) {
            console.log('🔄 Merge operation detected - using match results for Schema Mapping tab');
            displayEnhancedMapping(result.match_result);
        } else {
            // Fallback to merge data if no match result available
            displayEnhancedMapping(result.data);
        }
        // Display merged schema mappings
        displayMergedSchemaMappings(result.data);
        // Also update the main merged table in Schema Mapping tab with fresh data
        var mainMergedContainer = document.getElementById('mainMergedSchemaDisplay');
        var mergedSchemaSection = document.getElementById('mergedSchemaSection');
        console.log('📊 [DEBUG] mainMergedContainer found:', !!mainMergedContainer);
        console.log('📊 [DEBUG] mergedSchemaSection found:', !!mergedSchemaSection);
        if (mainMergedContainer) {
            mainMergedContainer.innerHTML = '';
            console.log('📊 [DEBUG] Calling createMergedSchemaTable with result.data keys:', Object.keys(result.data));
            var mergedSchemaTable = createMergedSchemaTable(result.data);
            console.log('📊 [DEBUG] mergedSchemaTable keys:', Object.keys(mergedSchemaTable));
            console.log('📊 [DEBUG] mergedSchemaTable key count:', Object.keys(mergedSchemaTable).length);
            if (Object.keys(mergedSchemaTable).length > 0) {
                console.log('🔄 Updating main merged table with fresh data from current run');
                var tableHTML = createEnhancedTable(mergedSchemaTable, 'main-merged', null);
                console.log('📊 [DEBUG] tableHTML length:', tableHTML ? tableHTML.length : 0);
                mainMergedContainer.innerHTML = tableHTML;
                // CRITICAL: Show the parent section so the table is visible!
                if (mergedSchemaSection) {
                    mergedSchemaSection.style.display = 'block';
                    console.log('📊 [DEBUG] Set mergedSchemaSection display to block');
                }
                // Apply styling immediately
                setTimeout(function () {
                    var checkbox = document.getElementById('sourceDataToggle');
                    var showData = checkbox ? checkbox.checked : true;
                    updateTableDataDisplay('mainMergedSchemaDisplay', showData);
                    addVerticalDashedLines('mainMergedSchemaDisplay');
                    console.log('📊 [DEBUG] Applied styling to merged table');
                }, 100);
            } else {
                console.log('⚠️ [DEBUG] mergedSchemaTable is empty! result.data:', result.data);
            }
        }
    } else {
        // This is a match operation - hide merge tabs and show match results
        // document.querySelector('[data-tab="merged-source"]').style.display = 'none';
        // document.querySelector('[data-tab="merged-target"]').style.display = 'none';
        // For match operations, use the main result data
        displayEnhancedMapping(result.data);

        // HITL: Show "Approve & Proceed to Merge" button for match operations
        console.log('📋 [HITL] Match operation detected - showing approval button');
        const approvalContainer = document.getElementById('proceedToMergeContainer');
        approvalContainer.style.display = 'block';

        // Update button text based on whether merge is pending
        const approvalTitle = approvalContainer.querySelector('h3');
        const approvalDesc = approvalContainer.querySelector('p');
        const approvalButton = approvalContainer.querySelector('button');

        if (pendingMergeConfig) {
            // Check if this is a partition merge workflow
            if (pendingMergeConfig.isPartitionMerge) {
                if (pendingMergeConfig.partitionPhase === 'match') {
                    approvalTitle.textContent = '📋 Phase 1: Schema Matching Complete';
                    approvalDesc.textContent = 'Review the matches above. Edit them in the Raw Results tab if needed, then proceed to Phase 2 (Schema Merge).';
                    approvalButton.innerHTML = '✓ Approve & Proceed to Schema Merge';
                } else if (pendingMergeConfig.partitionPhase === 'schema_merge') {
                    approvalTitle.textContent = '📋 Phase 2: Schema Merge Complete';
                    approvalDesc.textContent = 'Review the merged schema above. Edit it in the Raw Results tab if needed, then proceed to Phase 3 (Create Partitions).';
                    approvalButton.innerHTML = '✓ Approve & Create Partitions';
                } else if (pendingMergeConfig.partitionPhase === 'partitions_created') {
                    approvalTitle.textContent = '📋 Phase 3: Partitions Created';
                    approvalDesc.textContent = 'Partition information displayed in the Partitions tab. Proceed to Phase 4 (Merge Partitions).';
                    approvalButton.innerHTML = '✓ Approve & Merge Partitions';
                }
            } else {
                // Regular JSON-based merge
                approvalTitle.textContent = 'Schema Matching Complete - Merge Pending';
                approvalDesc.textContent = 'Review the matches above. Edit them in the Raw Results tab if needed, then proceed to merge with your approved matches.';
                approvalButton.innerHTML = '✓ Approve & Proceed to Merge';
            }
        } else {
            approvalTitle.textContent = 'Schema Matching Complete';
            approvalDesc.textContent = 'Matches displayed above. You can edit them in the Raw Results tab or proceed to merge if needed.';
            approvalButton.innerHTML = '→ Proceed to Merge (Optional)';
        }
    }
    document.getElementById('resultsContainer').style.display = 'block';
    switchTab('mapping');
    // window.lastResult already set at start of showResults
    // window.lastResult = result;
    if (result.metrics) {
        const prevOpType = window.lastMetrics ? window.lastMetrics.operation_type : null;
        const currOpType = result.metrics.operation_type;
        console.log('📊 [METRICS] prev op_type:', prevOpType, '→ curr op_type:', currOpType);

        const prevWasMatch = prevOpType === 'match';
        const currIsMerge = currOpType === 'merge' || currOpType === 'instance_merge';

        if (window.lastMetrics && prevWasMatch && currIsMerge) {
            console.log('🔄 [METRICS] Accumulating Match metrics into Merge metrics');

            // Preserve the match-specific values from the previous run
            result.metrics.match_generation_time = window.lastMetrics.total_generation_time || window.lastMetrics.match_generation_time || 0;
            result.metrics.match_input_tokens = window.lastMetrics.input_prompt_tokens || window.lastMetrics.match_input_tokens || 0;
            result.metrics.match_output_tokens = window.lastMetrics.output_tokens || window.lastMetrics.match_output_tokens || 0;
            result.metrics.match_api_cost = window.lastMetrics.api_call_cost || window.lastMetrics.match_api_cost || 0;
            result.metrics.matching_llm_used = window.lastMetrics.llm_model || window.lastMetrics.matching_llm_used || result.metrics.matching_llm_used;

            // The incoming merge result's totals represent only the merge step — store them in merge_X fields
            result.metrics.merge_generation_time = result.metrics.total_generation_time || result.metrics.merge_generation_time || 0;
            result.metrics.merge_input_tokens = result.metrics.merge_input_tokens || result.metrics.input_prompt_tokens || 0;
            result.metrics.merge_output_tokens = result.metrics.merge_output_tokens || result.metrics.output_tokens || 0;
            result.metrics.merge_api_cost = result.metrics.merge_api_cost || result.metrics.api_call_cost || 0;
            result.metrics.merge_llm_used = result.metrics.merge_llm_used || result.metrics.llm_model || result.metrics.matching_llm_used;

            // Accumulate totals so top-row shows combined pipeline cost
            result.metrics.total_generation_time = result.metrics.match_generation_time + result.metrics.merge_generation_time;
            result.metrics.input_prompt_tokens = result.metrics.match_input_tokens + result.metrics.merge_input_tokens;
            result.metrics.output_tokens = result.metrics.match_output_tokens + result.metrics.merge_output_tokens;
            result.metrics.api_call_cost = result.metrics.match_api_cost + result.metrics.merge_api_cost;
            result.metrics.total_tokens = result.metrics.input_prompt_tokens + result.metrics.output_tokens;

            // Recalculate tokens per second over the combined time
            if (result.metrics.total_generation_time > 0) {
                result.metrics.tokens_per_second = result.metrics.total_tokens / result.metrics.total_generation_time;
            }

            console.log('✅ [METRICS] Combined metrics:', {
                total_time: result.metrics.total_generation_time,
                total_cost: result.metrics.api_call_cost,
                match_tokens: result.metrics.match_input_tokens,
                merge_tokens: result.metrics.merge_input_tokens,
                matching_llm_used: result.metrics.matching_llm_used,
                merge_llm_used: result.metrics.merge_llm_used
            });
        }

        window.lastMetrics = result.metrics;

        // For partition workflow: accumulate metrics across phases
        if (pendingMergeConfig && pendingMergeConfig.isPartitionMerge) {
            if (!window.partitionPhaseMetrics) {
                window.partitionPhaseMetrics = { match: null, schemaMerge: null };
            }

            // Store metrics based on current phase
            if (pendingMergeConfig.partitionPhase === 'match') {
                window.partitionPhaseMetrics.match = result.metrics;
                console.log('📊 [PARTITION-METRICS] Stored Phase 1 (Match) metrics:', result.metrics);
            } else if (pendingMergeConfig.partitionPhase === 'schema_merge' ||
                pendingMergeConfig.partitionPhase === 'partitions_created') {
                window.partitionPhaseMetrics.schemaMerge = result.metrics;
                console.log('📊 [PARTITION-METRICS] Stored Phase 2 (Schema Merge) metrics:', result.metrics);
            }
        }

        // Update metrics display immediately
        displayMetrics(result.metrics);
    }
}

// HITL: Proceed to merge with approved/edited match results (handles multi-phase partition workflow)
async function proceedToMerge() {
    const statusEl = document.getElementById('mergeProgressStatus');
    const buttonEl = document.querySelector('#proceedToMergeContainer button');

    try {
        // Disable button and show progress
        buttonEl.disabled = true;
        buttonEl.style.opacity = '0.6';
        buttonEl.style.cursor = 'not-allowed';

        // Get the current result data (may have been edited by user)
        const jsonTextarea = document.getElementById('jsonOutput');
        const fullResultData = JSON.parse(jsonTextarea.value);

        // Get the original source and target data
        if (!sourceData || !targetData) {
            throw new Error('Source or target data is missing. Please re-upload the files.');
        }

        // Check if we have pending merge configuration
        if (!pendingMergeConfig) {
            throw new Error('No pending merge configuration found. Please re-run the process.');
        }

        // Check if this is a partition-based merge workflow
        if (pendingMergeConfig.isPartitionMerge) {
            await handlePartitionWorkflowPhase(fullResultData, statusEl, buttonEl);
        } else {
            await handleRegularMergeWorkflow(fullResultData, statusEl, buttonEl);
        }

    } catch (error) {
        console.error('❌ [HITL] Merge error:', error);
        statusEl.textContent = '❌ Error: ' + error.message;
        statusEl.style.color = '#c62828';

        // Re-enable button
        buttonEl.disabled = false;
        buttonEl.style.opacity = '1';
        buttonEl.style.cursor = 'pointer';
    }
}

// Handle regular (non-partition) merge workflow
async function handleRegularMergeWorkflow(fullResultData, statusEl, buttonEl) {
    statusEl.textContent = '⏳ Processing merge with approved matches...';
    statusEl.style.color = '#667eea';

    // Extract match results
    const approvedMatchResults = {
        HMD_matches: fullResultData.HMD_matches || [],
        VMD_matches: fullResultData.VMD_matches || []
    };

    console.log('📋 [HITL] Approved match results:', approvedMatchResults);

    // Prepare payload
    const payload = buildMergePayload(approvedMatchResults);

    // Call backend
    console.log('🚀 [HITL] Sending approved matches to merge step', payload);
    const response = await fetch(API_BASE_URL + '/process', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
    });

    const result = await response.json();

    if (result.success) {
        console.log('✅ [HITL] Merge completed with approved matches');
        statusEl.textContent = '✅ Merge completed successfully!';
        statusEl.style.color = '#2E7D32';

        // Clear pending merge config
        pendingMergeConfig = null;

        // Hide the proceed button
        document.getElementById('proceedToMergeContainer').style.display = 'none';

        // Show merge results
        showResults(result);
    } else {
        throw new Error(result.error || 'Merge operation failed');
    }
}

// Handle partition-based merge workflow (multi-phase)
async function handlePartitionWorkflowPhase(fullResultData, statusEl, buttonEl) {
    const currentPhase = pendingMergeConfig.partitionPhase;
    console.log(`📋 [HITL-PARTITION] Current phase: ${currentPhase}`);

    if (currentPhase === 'match') {
        // Phase 1 → Phase 2: Schema Match approved, proceed to Schema Merge
        await proceedToSchemaMerge(fullResultData, statusEl, buttonEl);
    } else if (currentPhase === 'schema_merge') {
        // Phase 2 → Phase 3: Schema Merge approved, create partitions
        await proceedToPartitionCreation(fullResultData, statusEl, buttonEl);
    } else if (currentPhase === 'partitions_created') {
        // Phase 3 → Phase 4: Partitions approved, merge all partitions
        await proceedToPartitionMerge(fullResultData, statusEl, buttonEl);
    }
}

// Phase 1 → 2: Schema Match approved, run Schema Merge
async function proceedToSchemaMerge(fullResultData, statusEl, buttonEl) {
    statusEl.textContent = '⏳ Phase 2: Running schema merge with approved matches...';
    statusEl.style.color = '#667eea';

    // Extract approved match results
    const approvedMatchResults = {
        HMD_matches: fullResultData.HMD_matches || [],
        VMD_matches: fullResultData.VMD_matches || []
    };

    console.log('📋 [HITL-PARTITION] Phase 1→2: Approved match results:', approvedMatchResults);

    // Build payload for schema merge
    const payload = buildMergePayload(approvedMatchResults);
    payload.operationType = 'merge';  // Force merge operation for schema merge

    // Call backend for schema merge
    const response = await fetch(API_BASE_URL + '/process', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
    });

    const result = await response.json();

    if (result.success) {
        console.log('✅ [HITL-PARTITION] Phase 2 complete: Schema merge done');
        statusEl.textContent = '✅ Phase 2: Schema merge complete!';
        statusEl.style.color = '#2E7D32';

        // Store merged schema for next phase
        window.approvedMergedSchema = result.data;

        // SKIP Phase 3 - use partitions already created during dropdown selection
        // Set phase directly to 'partitions_created' to proceed to Phase 4
        if (window.savedPartitionInfo) {
            console.log('📋 [HITL-PARTITION] Skipping Phase 3 - using saved partition info from dropdown selection');
            window.partitionInfo = window.savedPartitionInfo;
            pendingMergeConfig.partitionPhase = 'partitions_created';
        } else {
            // Fallback to Phase 3 if no saved partitions
            console.log('📋 [HITL-PARTITION] No saved partitions - proceeding to Phase 3');
            pendingMergeConfig.partitionPhase = 'schema_merge';
        }

        // Re-enable the button for next phase
        buttonEl.disabled = false;
        buttonEl.style.opacity = '1';
        buttonEl.style.cursor = 'pointer';

        // Show schema merge results (will show approval button for Phase 3 or 4)
        showResults(result);

    } else {
        throw new Error(result.error || 'Schema merge failed');
    }
}

// Phase 2 → 3: Schema Merge approved, create partitions
async function proceedToPartitionCreation(fullResultData, statusEl, buttonEl) {
    statusEl.textContent = '⏳ Phase 3: Creating partitions...';
    statusEl.style.color = '#667eea';

    console.log('📋 [HITL-PARTITION] Phase 2→3: Creating partitions with approved merged schema');

    // Store approved merged schema
    window.approvedMergedSchema = fullResultData;

    // Build payload for partition creation
    const payload = {
        sourceSchema: JSON.stringify(sourceData),
        targetSchema: JSON.stringify(targetData),
        schemaType: detectSchemaComplexity(sourceData) === 'complex' ? 'complex' : 'relational',
        approvedMergedSchema: fullResultData,
        mergeMethod: pendingMergeConfig.mergeMethod,  // Required by backend for partition validation
        operation: 'create_partitions'
    };

    // Call backend to create partitions
    const response = await fetch(API_BASE_URL + '/create-partitions', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
    });

    const result = await response.json();

    if (result.success) {
        console.log('✅ [HITL-PARTITION] Phase 3 complete: Partitions created');
        statusEl.textContent = '✅ Phase 3: Partitions created!';
        statusEl.style.color = '#2E7D32';

        // Store partition info for next phase
        window.partitionInfo = result.partitions;

        // Update partition phase
        pendingMergeConfig.partitionPhase = 'partitions_created';

        // Display partition info
        displayPartitionInfo(result.partitions);

        // Show partitions tab
        document.querySelector('[data-tab="partitions"]').style.display = 'block';
        switchTab('partitions');

        // Re-enable the button for Phase 4
        buttonEl.disabled = false;
        buttonEl.style.opacity = '1';
        buttonEl.style.cursor = 'pointer';

        // Update approval button text for Phase 4
        const approvalContainer = document.getElementById('proceedToMergeContainer');
        approvalContainer.style.display = 'block';

        const approvalTitle = approvalContainer.querySelector('h3');
        const approvalDesc = approvalContainer.querySelector('p');
        const approvalButton = approvalContainer.querySelector('button');

        approvalTitle.textContent = '📋 Phase 3: Partitions Created';
        approvalDesc.textContent = 'Partition information displayed in the Partitions tab. Review and proceed to Phase 4 (Merge Partitions).';
        approvalButton.innerHTML = '✓ Approve & Merge Partitions';
    } else {
        throw new Error(result.error || 'Partition creation failed');
    }
}

// Phase 3 → 4: Partitions approved, merge all partitions
async function proceedToPartitionMerge(fullResultData, statusEl, buttonEl) {
    statusEl.textContent = '⏳ Phase 4: Merging all partitions...';
    statusEl.style.color = '#667eea';

    console.log('📋 [HITL-PARTITION] Phase 3→4: Merging partitions with approved schema');

    // Show the Partitions tab with the workflow visual
    if (window.partitionInfo) {
        document.querySelector('[data-tab="partitions"]').style.display = 'block';
        displayPartitionInfo(window.partitionInfo);
    }

    // IMPORTANT: Update window.approvedMergedSchema with user's edits from Raw Results tab
    // fullResultData contains the user-edited JSON from the textarea
    window.approvedMergedSchema = fullResultData;
    console.log('📋 [HITL-PARTITION] Using user-edited schema:', Object.keys(fullResultData));

    // Build payload for partition merge - use fullResultData which has user edits
    const payload = {
        sourceSchema: JSON.stringify(sourceData),
        targetSchema: JSON.stringify(targetData),
        schemaType: detectSchemaComplexity(sourceData) === 'complex' ? 'complex' : 'relational',
        approvedMergedSchema: fullResultData,  // Use the user-edited data, not window.approvedMergedSchema
        partitionInfo: window.partitionInfo,
        mergeLLM: pendingMergeConfig.mergeLLM,
        matchingLLM: pendingMergeConfig.matchingLLM,  // Include matching LLM for metrics
        parameters: getParameterValues(),
        operation: 'merge_partitions',
        // Include Phase 1 schema mapping for precise VMD/HMD key alignment in stacking
        matchResult: window.lastResult?.match_result || null,
        // Include accumulated phase metrics for proper aggregation
        phaseMetrics: window.partitionPhaseMetrics || null
    };

    console.log('📊 [PARTITION-METRICS] Sending phase metrics to backend:', window.partitionPhaseMetrics);


    // Call backend to merge all partitions
    const response = await fetch(API_BASE_URL + '/merge-partitions', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
    });

    const result = await response.json();

    if (result.success) {
        console.log('✅ [HITL-PARTITION] Phase 4 complete: All partitions merged');
        statusEl.textContent = '✅ Phase 4: Partition merge complete!';
        statusEl.style.color = '#2E7D32';

        // Clear pending merge config - workflow complete
        pendingMergeConfig = null;

        // Hide the proceed button
        document.getElementById('proceedToMergeContainer').style.display = 'none';

        // Show final stacked results
        showResults(result);
    } else {
        throw new Error(result.error || 'Partition merge failed');
    }
}

// Helper: Build merge payload from configuration
function buildMergePayload(approvedMatchResults) {
    const sourceComplexity = detectSchemaComplexity(sourceData);
    const targetComplexity = detectSchemaComplexity(targetData);
    const schemaType = (sourceComplexity === 'complex' || targetComplexity === 'complex') ? 'complex' : 'relational';

    const payload = {
        sourceSchema: JSON.stringify(sourceData),
        targetSchema: JSON.stringify(targetData),
        schemaType: schemaType,
        processingType: pendingMergeConfig.processingType || 'operator',
        operationType: (() => {
            const op = window._automatedMergeOp || pendingMergeConfig.mergeOperation || 'merge';
            if (window._automatedMergeOp) {
                console.log(`🔒 [MERGE-PAYLOAD] Using automated override: "${op}"`);
                window._automatedMergeOp = null; // consume once
            }
            return op;
        })(),
        llmModel: pendingMergeConfig.mergeLLM || 'gemini-1.5-flash',
        parameters: getParameterValues(),
        useMergeMultiStep: pendingMergeConfig.mergeMethod === 'multi_step',
        flexibleConfig: {
            matchOperation: pendingMergeConfig.matchOperation || 'operator',
            schemaMatchingType: pendingMergeConfig.schemaMatchingType || 'json_default',
            matchingLLM: pendingMergeConfig.matchingLLM,
            mergeOperation: pendingMergeConfig.mergeOperation,
            mergeMethod: pendingMergeConfig.mergeMethod,
            mergeLLM: pendingMergeConfig.mergeLLM,
            mergeValueStrategy: pendingMergeConfig.mergeValueStrategy || 'delimited'
        },
        preApprovedMatchResult: approvedMatchResults,
        // Pass saved match-phase metrics so backend can build combined match+merge metrics
        previousMatchMetrics: window.lastMetrics || null
    };

    // Add API keys if available
    const apiKeys = getApiKeysForRequest();
    if (Object.keys(apiKeys).length > 0) {
        payload.apiKeys = apiKeys;
    }

    return payload;
}

// Display partition information in the Partitions tab with visual workflow
function displayPartitionInfo(partitions) {
    const container = document.getElementById('partitionWorkflowContent');
    if (!container) {
        console.warn('Partition workflow container not found');
        return;
    }

    const numPartitions = partitions.source_partitions.length;
    const sourceRows = partitions.source_partitions.map(p => `${p.start_row}-${p.end_row}`);
    const targetRows = partitions.target_partitions.map(p => `${p.start_row}-${p.end_row}`);

    // Helper function to generate tooltip content for partition data
    function generateTooltipContent(partition, type, index) {
        const startRow = partition.start_row;
        const endRow = partition.end_row;
        const rowCount = partition.row_count || (endRow - startRow);

        // Get the table name
        const tableName = partition.table_name || (type === 'Source' ? 'Table1' : 'Table2');

        // FIXED: Use partition's pre-sliced schema data instead of re-slicing from original data
        // The backend already correctly sliced VMD and Data together with proper alignment
        const partitionSchema = partition.schema || {};
        const vmdKey = `${tableName}.VMD`;
        const dataKey = `${tableName}.Data`;
        const hmdKey = `${tableName}.HMD`;

        // Get pre-sliced VMD and Data from partition (already aligned by backend)
        const partitionVmd = partitionSchema[vmdKey] || [];
        const partitionData = partitionSchema[dataKey] || [];
        const hmd = partitionSchema[hmdKey] || [];

        // Flatten the pre-sliced VMD hierarchy to get actual row names
        // NOTE: The partition VMD only contains children (no parent empty rows in Data)
        const flatVmd = [];
        const vmdIsParent = []; // Track which VMD rows are parents (should have no data)
        partitionVmd.forEach(vmdItem => {
            if (vmdItem && typeof vmdItem === 'object') {
                // Check if this is a REAL parent (has non-empty children array)
                const hasChildren = vmdItem.children && Array.isArray(vmdItem.children) && vmdItem.children.length > 0;

                // Get the attribute name for parent
                const attrKey = Object.keys(vmdItem).find(k => k.startsWith('attribute'));
                if (attrKey && vmdItem[attrKey]) {
                    // Add parent as a category header
                    flatVmd.push(vmdItem[attrKey]);
                    vmdIsParent.push(hasChildren); // Only mark as parent if has children
                }

                // Then add children if present
                if (hasChildren) {
                    vmdItem.children.forEach(child => {
                        const childKey = Object.keys(child).find(k => k.includes('attribute'));
                        if (childKey) {
                            flatVmd.push(child[childKey]);
                            vmdIsParent.push(false); // Mark as child (data row)
                        }
                    });
                }
            } else if (typeof vmdItem === 'string') {
                flatVmd.push(vmdItem);
                vmdIsParent.push(false); // String items are data rows
            }
        });

        // Use the flattened VMD and partition data directly (already correctly aligned)
        const slicedVmd = flatVmd;
        const slicedData = partitionData;
        const slicedIsParent = vmdIsParent;

        // Build header row from HMD (flatten children but keep track of parents)
        let headerCols = [];
        let parentHeaders = []; // Track parent headers for hierarchical display
        if (hmd.length > 0) {
            hmd.forEach(h => {
                if (h.children && h.children.length > 0) {
                    // Get parent attribute name
                    const parentAttrKey = Object.keys(h).find(k => k.startsWith('attribute'));
                    const parentName = parentAttrKey ? h[parentAttrKey] : '';

                    // Include ALL children (removed slice limit)
                    h.children.forEach(c => {
                        const childKey = Object.keys(c).find(k => k.includes('attribute'));
                        if (childKey) {
                            headerCols.push(c[childKey]);
                            parentHeaders.push(parentName); // Track which parent each column belongs to
                        }
                    });
                } else {
                    const attrKey = Object.keys(h).find(k => k.startsWith('attribute'));
                    if (attrKey && h[attrKey]) {
                        headerCols.push(h[attrKey]);
                        parentHeaders.push(null); // No parent for flat attributes
                    }
                }
            });
        }
        // Increase limit to 8 data columns for better visibility
        const maxCols = 8;
        headerCols = headerCols.slice(0, maxCols);
        parentHeaders = parentHeaders.slice(0, maxCols);

        // Start building HTML - add close button to header
        let tooltipHtml = `<button class="tooltip-close" onclick="event.stopPropagation(); this.closest('.partition-tooltip').classList.remove('active');">✕</button>`;
        tooltipHtml += `<div class="tooltip-header">📋 ${type} Partition ${index + 1}</div>`;
        tooltipHtml += `<div class="tooltip-info">Rows: ${startRow} - ${endRow} · ${rowCount} rows</div>`;

        // Build scrollable table
        tooltipHtml += `<div class="tooltip-table-container"><table class="tooltip-table">`;

        // Check if we have hierarchical headers (parents)
        const hasParentRow = parentHeaders.some(p => p !== null);

        // Parent header row (if hierarchical)
        if (hasParentRow) {
            tooltipHtml += `<thead><tr class="parent-header-row">`;
            tooltipHtml += `<th rowspan="2">VMD Attribute</th>`;

            // Group consecutive columns by same parent
            let currentParent = null;
            let colspan = 0;
            let parentCells = [];

            for (let i = 0; i < parentHeaders.length; i++) {
                const parent = parentHeaders[i] || '';
                if (parent === currentParent) {
                    colspan++;
                } else {
                    if (currentParent !== null) {
                        parentCells.push({ name: currentParent, colspan: colspan });
                    }
                    currentParent = parent;
                    colspan = 1;
                }
            }
            // Push last group
            if (currentParent !== null) {
                parentCells.push({ name: currentParent, colspan: colspan });
            }

            parentCells.forEach(pc => {
                const displayName = pc.name ? (pc.name.length > 25 ? pc.name.substring(0, 25) + '...' : pc.name) : '';
                tooltipHtml += `<th colspan="${pc.colspan}" title="${pc.name || ''}">${displayName}</th>`;
            });
            tooltipHtml += `</tr>`;

            // Child header row
            tooltipHtml += `<tr class="child-header-row">`;
            for (let i = 0; i < headerCols.length; i++) {
                const colName = String(headerCols[i] || `Col${i + 1}`);
                const displayName = colName.length > 10 ? colName.substring(0, 10) + '...' : colName;
                tooltipHtml += `<th title="${colName}">${displayName}</th>`;
            }
            tooltipHtml += `</tr></thead>`;
        } else {
            // Simple header row (no hierarchy)
            tooltipHtml += `<thead><tr>`;
            tooltipHtml += `<th>VMD Attribute</th>`;
            for (let i = 0; i < headerCols.length; i++) {
                const colName = String(headerCols[i] || `Col${i + 1}`).substring(0, 10);
                tooltipHtml += `<th>${colName}${String(headerCols[i]).length > 10 ? '...' : ''}</th>`;
            }
            tooltipHtml += `</tr></thead>`;
        }

        // Data rows - use separate dataIndex since partition counts only children (parents don't consume data rows)
        tooltipHtml += `<tbody>`;
        let dataIndex = 0; // Separate index for data array (only increments for children)
        const maxVmdRows = Math.min(slicedVmd.length, 15);

        for (let j = 0; j < maxVmdRows; j++) {
            const vmdName = slicedVmd[j] || `Row ${startRow + j}`;
            const isParentRow = slicedIsParent[j] || false;

            if (isParentRow) {
                // Parent row: display as category header spanning all columns (NO data consumption)
                tooltipHtml += `<tr class="parent-vmd-row">`;
                tooltipHtml += `<td class="vmd-cell parent-cell" colspan="${headerCols.length + 1}" title="${vmdName}" style="background:#e8f5e9;font-weight:bold;color:#2E7D32;">${String(vmdName).substring(0, 40)}${String(vmdName).length > 40 ? '...' : ''}</td>`;
                tooltipHtml += `</tr>`;
                // NOTE: Parent rows DON'T increment dataIndex because partition row counting is children-only
            } else {
                // Child row: display with data values
                if (dataIndex >= slicedData.length) break; // No more data

                tooltipHtml += `<tr>`;
                tooltipHtml += `<td class="vmd-cell" title="${vmdName}">${String(vmdName).substring(0, 22)}${String(vmdName).length > 22 ? '...' : ''}</td>`;

                // Data cells - use dataIndex instead of j
                const rowData = slicedData[dataIndex] || [];
                const dataArr = Array.isArray(rowData) ? rowData : Object.values(rowData);
                for (let k = 0; k < headerCols.length; k++) {
                    const cellVal = String(dataArr[k] || '');
                    tooltipHtml += `<td class="data-cell" title="${cellVal}">${cellVal.substring(0, 10)}${cellVal.length > 10 ? '...' : ''}</td>`;
                }
                tooltipHtml += `</tr>`;
                dataIndex++; // Only increment for data rows (children)
            }
        }

        if (slicedData.length > dataIndex) {
            tooltipHtml += `<tr><td colspan="${headerCols.length + 1}" style="text-align:center;color:#888;font-style:italic;">... ${slicedData.length - dataIndex} more rows</td></tr>`;
        }

        tooltipHtml += `</tbody></table></div>`;

        return tooltipHtml;
    }

    // Build the visual workflow HTML
    let html = `
        <div class="workflow-container" style="display:flex;justify-content:center;gap:5px;">
            <!-- Source Side -->
            <div class="workflow-section">
                <h4>📊 SOURCE TABLE</h4>
                <div class="table-box">Table 1</div>
                <div class="down-arrow">↓</div>
                <div class="partition-list">
    `;

    // Source partition boxes (show max 5 with ellipsis)
    const maxShow = Math.min(numPartitions, 5);
    for (let i = 0; i < maxShow; i++) {
        const srcPartition = partitions.source_partitions[i];
        const tooltipContent = generateTooltipContent(srcPartition, 'Source', i);
        html += `<div class="partition-box source" onclick="togglePartitionTooltip(event, this)">P${i + 1}<br><small>rows ${sourceRows[i]}</small><div class="partition-tooltip">${tooltipContent}</div></div>`;
    }
    if (numPartitions > 5) {
        html += `<div class="ellipsis">⋮</div>`;
    }

    html += `
                </div>
            </div>

            <!-- Plus Sign Column -->
            <div class="workflow-section" style="padding-top:85px;">
                <div class="partition-list">
    `;

    for (let i = 0; i < maxShow; i++) {
        html += `<div class="plus-sign" style="height:52px;display:flex;align-items:center;justify-content:center;font-size:28px;font-weight:bold;color:#4a5568;">+</div>`;
    }

    html += `
                </div>
            </div>

            <!-- Target Side -->
            <div class="workflow-section">
                <h4>📊 TARGET TABLE</h4>
                <div class="table-box">Table 2</div>
                <div class="down-arrow">↓</div>
                <div class="partition-list">
    `;

    // Target partition boxes
    for (let i = 0; i < maxShow; i++) {
        const tgtPartition = partitions.target_partitions[i];
        const tooltipContent = generateTooltipContent(tgtPartition, 'Target', i);
        html += `<div class="partition-box target" onclick="togglePartitionTooltip(event, this)">P${i + 1}'<br><small>rows ${targetRows[i]}</small><div class="partition-tooltip">${tooltipContent}</div></div>`;
    }
    if (numPartitions > 5) {
        html += `<div class="ellipsis">⋮</div>`;
    }

    html += `
                </div>
            </div>

            <!-- Arrow Column -->
            <div class="workflow-section" style="padding-top:85px;">
                <div class="partition-list">
    `;

    for (let i = 0; i < maxShow; i++) {
        html += `<div class="arrow-sign" style="height:52px;display:flex;align-items:center;justify-content:center;font-size:28px;font-weight:bold;color:#4a5568;">→</div>`;
    }

    html += `
                </div>
            </div>

            <!-- Merged Results -->
            <div class="workflow-section">
                <h4>🔗 MERGED PARTITIONS</h4>
                <div style="height:44px;"></div>
                <div class="down-arrow" style="visibility:hidden;">↓</div>
                <div class="partition-list">
    `;

    // Merged partition boxes
    for (let i = 0; i < maxShow; i++) {
        html += `<div class="partition-box merged">PS${i + 1}</div>`;
    }
    if (numPartitions > 5) {
        html += `<div class="ellipsis">⋮</div>`;
    }

    html += `
                </div>
            </div>
        </div>

        <!-- Statistics -->
        <div style="text-align:center;margin-top:25px;">
            <div class="stats-box">
                <span>📦 <strong>Total Partitions:</strong> ${numPartitions}</span>
                <span>|</span>
                <span>📏 <strong>Source Rows per Partition:</strong> ~${Math.round(sourceRows.map(r => { const parts = r.split('-'); return parseInt(parts[1]) - parseInt(parts[0]) + 1; }).reduce((a, b) => a + b, 0) / numPartitions)}</span>
            </div>
        </div>

        <!-- Final Result Arrow -->
        <div class="final-result">
            <div class="down-arrow" style="font-size:30px;">⬇</div>
            <div class="final-box">📋 Stacked Merge Table</div>
        </div>
    `;

    container.innerHTML = html;
}

// Toggle partition tooltip on click (instead of hover)
function togglePartitionTooltip(event, element) {
    event.stopPropagation();

    const tooltip = element.querySelector('.partition-tooltip');
    if (!tooltip) return;

    // Close all other tooltips first
    document.querySelectorAll('.partition-tooltip.active').forEach(t => {
        if (t !== tooltip) t.classList.remove('active');
    });

    // Toggle this tooltip
    tooltip.classList.toggle('active');
}

// Close tooltips when clicking outside
document.addEventListener('click', function (event) {
    if (!event.target.closest('.partition-box') && !event.target.closest('.partition-tooltip')) {
        document.querySelectorAll('.partition-tooltip.active').forEach(t => {
            t.classList.remove('active');
        });
    }
});

// Apply edited JSON from Raw Results tab
function applyEditedJson() {
    const statusEl = document.getElementById('jsonEditStatus');
    const jsonTextarea = document.getElementById('jsonOutput');

    try {
        // Parse the edited JSON
        const editedData = JSON.parse(jsonTextarea.value);

        // Update the stored result
        if (window.lastResult) {
            window.lastResult.data = editedData;
            // CRITICAL: Overwrite the cached match_result too, otherwise switchTab('mapping')
            // will silently restore the old ML mappings and ignore the user's edits!
            if (window.lastResult.match_result) {
                window.lastResult.match_result = editedData;
            }
        }

        // Switch to Schema Mapping tab to see changes first so bounding boxes are valid
        switchTab('mapping');

        // Re-render the mappings with edited data after tab transition gives the DOM time to settle
        setTimeout(() => {
            console.log('✅ Applying user-edited mappings from Raw Results');
            displayEnhancedMapping(editedData);

            // If it's a merge operation, also update merged schema mappings
            const hmdMerged = editedData.HMD_Merged_Schema || (editedData.Merged_Schema && editedData.Merged_Schema.HMD_Merged_Schema);
            const vmdMerged = editedData.VMD_Merged_Schema || (editedData.Merged_Schema && editedData.Merged_Schema.VMD_Merged_Schema);

            if (hmdMerged || vmdMerged) {
                displayMergedSchemaMappings(editedData);

                // Update main merged table
                const mainMergedContainer = document.getElementById('mainMergedSchemaDisplay');
                if (mainMergedContainer) {
                    mainMergedContainer.innerHTML = '';
                    const mergedSchemaTable = createMergedSchemaTable(editedData);
                    if (Object.keys(mergedSchemaTable).length > 0) {
                        mainMergedContainer.innerHTML = createEnhancedTable(mergedSchemaTable, 'main-merged', null);
                        setTimeout(function () {
                            const checkbox = document.getElementById('sourceDataToggle');
                            const showData = checkbox ? checkbox.checked : true;
                            updateTableDataDisplay('mainMergedSchemaDisplay', showData);
                            addVerticalDashedLines('mainMergedSchemaDisplay');
                        }, 100);
                    }
                }
            }

            // Show success message
            statusEl.textContent = '✅ Changes applied successfully!';
            statusEl.style.color = '#2E7D32';
            setTimeout(() => { statusEl.textContent = ''; }, 3000);
        }, 300);
        setTimeout(() => { statusEl.textContent = ''; }, 3000);

    } catch (error) {
        // Show error message
        console.error('JSON parse error:', error);
        statusEl.textContent = '❌ Invalid JSON: ' + error.message;
        statusEl.style.color = '#c62828';
    }
}

// Simple and clean connection drawing
function drawConnectionLines(resultData) {
    const svg = document.getElementById('connectionOverlay');
    if (!svg) return;
    svg.innerHTML = '';
    const container = document.querySelector('.mapping-tables-container');
    if (!container) return;
    const rect = container.getBoundingClientRect();
    svg.setAttribute('viewBox', `0 0 ${rect.width} ${rect.height}`);
    // For merge operations, we might not have direct matches to draw
    if (resultData.Merged_Schema && resultData.Merged_Schema.length > 0) {
        // Don't draw connections for merge results
        return;
    }
    const hmd = Array.isArray(resultData.HMD_matches) ? resultData.HMD_matches : [];
    const vmd = Array.isArray(resultData.VMD_matches) ? resultData.VMD_matches : [];
    // Draw clean, simple connections
    drawCleanHmdConnections(svg, hmd, rect);
    drawCleanVmdConnections(svg, vmd, rect);
}
// Clean HMD connections - ensure ALL mappings start above tables, including the first one
// Clean HMD connections - ensure ALL mappings start above tables, including the first one
function drawCleanHmdConnections(svg, hmdMatches, rect) {
    if (!Array.isArray(hmdMatches) || !hmdMatches.length) return;
    const sourceTable = _tableEl('source');
    const targetTable = _tableEl('target');
    if (!sourceTable || !targetTable) {
        return;
    }
    const sourceRect = sourceTable.getBoundingClientRect();
    const targetRect = targetTable.getBoundingClientRect();
    // CRITICAL: Calculate routing Y that is ABOVE the tables, not within them
    // Find the topmost point of both tables
    const topmostTableY = Math.min(sourceRect.top, targetRect.top);
    // Route the horizontal lines ABOVE the tables with proper clearance
    // Start the FIRST mapping at a good distance above the table
    // FIXED: Force routing well above tables - use a fixed position approach
    const tableTopInContainer = topmostTableY - rect.top;
    const firstLaneY = Math.max(30, tableTopInContainer - 50); // Reduced clearance for compact appearance
    const minDistanceAbove = 25; // Minimum distance any HMD line must stay above tables
    // Optimized lane spacing for beautiful, compact appearance
    const laneSpacing = 20; // Reduced from 25 to 20 for tighter, more beautiful spacing
    hmdMatches.forEach((match, index) => {
        const srcEl = _findInSide('source', 'header', match.source);
        const tgtEl = _findInSide('target', 'header', match.target);
        if (!srcEl || !tgtEl) {
            return;
        }
        const srcBounds = srcEl.getBoundingClientRect();
        const tgtBounds = tgtEl.getBoundingClientRect();
        // Start from center of source column and end at center of target column
        const startX = srcBounds.left + srcBounds.width / 2 - rect.left;
        const startY = srcBounds.top - rect.top;
        const endX = tgtBounds.left + tgtBounds.width / 2 - rect.left;
        const endY = tgtBounds.top - rect.top;
        // FIXED: ALL mappings start above tables with individual lane separation
        // First mapping starts at firstLaneY, subsequent ones get additional spacing
        const laneY = firstLaneY - (index * laneSpacing);
        // Calculate the minimum safe Y position for this specific lane (same fix as merge tabs)
        const sourceTableTop = srcBounds.top - rect.top;
        const targetTableTop = tgtBounds.top - rect.top;
        const tablesTop = Math.min(sourceTableTop, targetTableTop);
        const minSafeY = tablesTop - minDistanceAbove - (index * laneSpacing);
        // Use the higher position (more negative Y = higher on screen) while maintaining lane separation
        const routingY = Math.min(laneY, minSafeY); // Each lane maintains its individual offset
        console.log(`🟢 Schema Mapping HMD ${index}:`, {
            lane: index,
            laneY: laneY,
            minSafeY: minSafeY,
            routingY: routingY,
            separation: index > 0 ? Math.abs(routingY - (firstLaneY - ((index - 1) * laneSpacing))) : 0
        });
        // Path: up → right (above table) → down
        const path = `M ${startX} ${startY} ` +           // Start at source header
            `L ${startX} ${routingY} ` +          // Go UP above table (guaranteed)
            `L ${endX} ${routingY} ` +            // Go RIGHT above table (outside table area)
            `L ${endX} ${endY}`;                  // Go DOWN to target header
        // Use green color for HMD connections
        const color = '#66bb6a';
        _drawPath(svg, path, color, 3, 0.95);
        // Connection dots at start and end points
        _drawConnectionIndicator(svg, startX, startY, color);
        _drawConnectionIndicator(svg, endX, endY, color);
    });
}
// Lane spacing constants (same as appv11.py)
const LANE_MIN_GAP = 10;   // px
const LANE_MAX_GAP = 22;   // px
const LANE_MARGIN_TOP = 10; // px from very top of overlay
const LANE_CLEARANCE = 28; // px above the topmost involved header
/**
 * Compute a good lane baseline and spacing for all header lines.
 * Returns { baseY, gap } in overlay coords.
 * Same logic as appv11.py
 */
function _computeLaneGeometry(hmdPairs, containerRect) {
    // find the smallest y (top) among all involved source/target header cells
    let topMost = Number.POSITIVE_INFINITY;
    (hmdPairs || []).forEach(m => {
        const se = _findInSide('source', 'header', m.source);
        const te = _findInSide('target', 'header', m.target);
        if (!se || !te) return;
        const sr = se.getBoundingClientRect();
        const tr = te.getBoundingClientRect();
        topMost = Math.min(topMost, sr.top - containerRect.top, tr.top - containerRect.top);
    });
    if (!isFinite(topMost)) {
        // fallback
        return { baseY: 40, gap: 16 };
    }
    // put the first lane a bit above the top row and fan upwards
    const baseY = Math.max(LANE_MARGIN_TOP + 10, topMost - LANE_CLEARANCE);
    // choose a gap that fits all lanes in the space above baseY
    // (if there isn't much headroom, the gap shrinks but never below LANE_MIN_GAP)
    return function (totalLanes) {
        const headroom = Math.max(0, baseY - LANE_MARGIN_TOP);
        const idealGap = totalLanes > 1 ? Math.floor(headroom / totalLanes) : LANE_MAX_GAP;
        const gap = Math.max(LANE_MIN_GAP, Math.min(LANE_MAX_GAP, idealGap));
        return { baseY, gap };
    };
}
// Clean VMD connections - left → down → right → up → right routing pattern
function drawCleanVmdConnections(svg, vmdMatches, rect) {
    if (!Array.isArray(vmdMatches) || !vmdMatches.length) return;
    const sourceTable = _tableEl('source');
    const targetTable = _tableEl('target');
    if (!sourceTable || !targetTable) return;
    const sourceRect = sourceTable.getBoundingClientRect();
    const targetRect = targetTable.getBoundingClientRect();

    // Calculate routing coordinates using minimal space for efficient routing
    const leftMargin = 50; // Further reduced left routing space
    const rightMargin = 30; // Further reduced right routing space
    const bottomMargin = 40; // Significantly reduced bottom routing space

    // Force ALL lines to start from the LEFT edge of the source table
    const sourceLeftX = sourceRect.left - rect.left;
    const leftRoutingX = sourceLeftX - leftMargin;

    // Bottom routing area (below both tables) - ensure we stay within container height
    const bottomRoutingY = Math.min(rect.height - 50, Math.max(sourceRect.bottom, targetRect.bottom) - rect.top + bottomMargin);

    // Middle routing area (between tables) - ensure ALL lines go through this area
    const middleRoutingX = sourceRect.right + (targetRect.left - sourceRect.right) / 2 - rect.left;
    const rightRoutingX = Math.min(rect.width - 20, rect.width - rightMargin);
    const targetLeftX = targetRect.left - rect.left;
    const laneSpacing = 15; // Further reduced spacing for more compact VMD routing

    // Helper to extract child name from hierarchical VMD path
    function extractVmdChildName(vmdPath) {
        if (!vmdPath) return vmdPath;
        const separatorIndex = vmdPath.lastIndexOf('.');
        if (separatorIndex !== -1) {
            return vmdPath.substring(separatorIndex + 1); // Skip ":."
        }
        return vmdPath; // No hierarchy, return as-is
    }

    const connectionData = [];
    const colors = ['#e57373', '#f06292', '#ba68c8', '#9575cd', '#7986cb', '#64b5f6', '#4db6ac', '#81c784', '#ffb74d'];

    // Pre-calculate all coordinates
    vmdMatches.forEach((match, index) => {
        const sourceRowName = extractVmdChildName(match.source);
        const targetRowName = extractVmdChildName(match.target);

        const sourceRow = _findInSide('source', 'row', sourceRowName);
        const targetRow = _findInSide('target', 'row', targetRowName);
        if (!sourceRow || !targetRow) return;

        const sourceRowRect = sourceRow.getBoundingClientRect();
        const targetRowRect = targetRow.getBoundingClientRect();

        // Center Y coordinates relative to container
        const sourceY = (sourceRowRect.top + sourceRowRect.height / 2) - rect.top;
        const targetY = (targetRowRect.top + targetRowRect.height / 2) - rect.top;
        const color = colors[index % colors.length];

        connectionData.push({ match, sourceY, targetY, color });
    });

    // Ensure the bus lanes don't cross! Sort by source Y so highest rows get the furthest outer lane
    connectionData.sort((a, b) => a.sourceY - b.sourceY);

    // Draw lines sequentially to prevent SVG overlap
    connectionData.forEach((conn, index) => {
        // Each connection gets its own sorted lane to avoid crossover 
        const laneOffset = index * laneSpacing;

        // Optimized routing: use fixed bottom area, vary only horizontal offset
        const routingBottom = bottomRoutingY + Math.min(laneOffset, 60);

        // Create the left → down → right → up → right path with compact routing
        const path = `M ${sourceLeftX} ${conn.sourceY} ` +
            `L ${leftRoutingX + laneOffset} ${conn.sourceY} ` +
            `L ${leftRoutingX + laneOffset} ${routingBottom} ` +
            `L ${middleRoutingX + laneOffset} ${routingBottom} ` +
            `L ${middleRoutingX + laneOffset} ${conn.targetY} ` +
            `L ${targetLeftX} ${conn.targetY}`;

        _drawPath(svg, path, conn.color, 2.5, 0.9);
        _drawConnectionIndicator(svg, sourceLeftX, conn.sourceY, conn.color);
        _drawConnectionIndicator(svg, targetLeftX, conn.targetY, conn.color);
    });
}
// Helper function to draw connection indicators
function _drawConnectionIndicator(svg, x, y, color) {
    const circle = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
    circle.setAttribute('cx', x);
    circle.setAttribute('cy', y);
    circle.setAttribute('r', '4');
    circle.setAttribute('fill', color);
    circle.setAttribute('opacity', '0.8');
    svg.appendChild(circle);
}
function _rowCenterY(side, rowName, containerRect) {
    const tr = _findInSide(side, 'row', rowName);
    if (!tr) return null;
    const r = tr.getBoundingClientRect();
    // Get the table container to ensure consistent reference point
    const tableContainer = document.getElementById(side === 'source' ? 'sourceTableDisplay' : 'targetTableDisplay');
    const tableRect = tableContainer.getBoundingClientRect();
    // Calculate center Y relative to the main container, but account for table-specific offsets
    const centerY = (r.top + r.height / 2) - containerRect.top;
    return centerY;
}
function _getRowLabelLeftX(side, rowName, containerRect) {
    const tr = _findInSide(side, 'row', rowName);
    if (!tr) return null;
    const labelCell = tr.querySelector('td.vmd-cell') || tr.querySelector('td');
    if (!labelCell) return null;
    const cellRect = labelCell.getBoundingClientRect();
    // Calculate X position relative to container, ensuring we start from the actual cell edge
    const leftX = cellRect.left - containerRect.left;
    return leftX;
}
function _findInSide(side, dataAttr, value) {
    const root = document.getElementById(side === 'source' ? 'sourceTableDisplay' : 'targetTableDisplay');
    if (!root) {
        console.warn(`Could not find root element for ${side} side`);
        return null;
    }
    // Clean the value for CSS selector
    const cleanValue = String(value).trim();
    // Try direct attribute match first
    let element = root.querySelector(`[data-${dataAttr}="${cleanValue}"]`);
    if (!element) {
        // Try with CSS.escape as fallback
        try {
            const escapedValue = CSS.escape(cleanValue);
            element = root.querySelector(`[data-${dataAttr}="${escapedValue}"]`);
        } catch (e) { }
    }

    // Log if exact match failed
    if (!element) console.log(`[MAP_DEBUG] Exact match failed for ${side} ${dataAttr}="${cleanValue}". Falling back to fuzzy.`);

    // If still no match, try fuzzy matching for rows (with VMD hierarchy support)
    if (!element && dataAttr === 'row') {
        element = _findRowFuzzyWithVMD(root, cleanValue);
    }
    // If still no match, try fuzzy matching for headers
    if (!element && dataAttr === 'header') {
        element = _findHeaderFuzzy(root, cleanValue);
    }
    if (!element) {
        console.warn(`[MAP_DEBUG] Could not find ANY element for ${side} ${dataAttr}="${cleanValue}"`);
    } else {
        console.log(`[MAP_DEBUG] Successfully resolved ${side} ${dataAttr}="${cleanValue}" to element:`,
            dataAttr === 'header' ? element.getAttribute('data-header') : element.getAttribute('data-row'));
    }
    return element;
}
// Enhanced row finding with VMD hierarchy support
function _findRowFuzzyWithVMD(root, searchValue) {
    let originalNeedle = searchValue.toLowerCase();
    let needle = originalNeedle;
    let categoryPart = null;

    // extract child part immediately to prevent false fuzzy matches on parent names
    const separatorIndex = needle.indexOf(':.');
    if (separatorIndex !== -1) {
        // e.g., "Financial Data (in millions...):.Operating revenues"
        categoryPart = needle.substring(0, separatorIndex).split('.').pop();
        needle = needle.substring(separatorIndex + 2); // Skip ":." 
    } else if (needle.includes('.')) {
        // e.g., "Table1.VMD.Age.<65"
        const parts = needle.split('.');
        if (parts.length >= 2) {
            categoryPart = parts[parts.length - 2];
            needle = parts[parts.length - 1];
        }
    }

    // Now needle is just the actual row target, like "<65" or "White"
    needle = needle.trim();
    if (categoryPart) categoryPart = categoryPart.trim();

    // 1. Precise Parent-Child DOM Matching
    // If we have a category part, try to find the EXACT child under that specific category
    if (categoryPart) {
        const categoryRows = root.querySelectorAll('tr[id*="-vmd-category-"]');
        let categoryIndex = null;

        // Find category row first
        for (const catTr of categoryRows) {
            const catVal = (catTr.getAttribute('data-row') || '').trim().toLowerCase();
            if (catVal === categoryPart || _isSimilar(catVal, categoryPart)) {
                // Found category! Extract its index from ID (e.g. "source-vmd-category-5")
                const match = catTr.id.match(/-vmd-category-(\d+)/);
                if (match) {
                    categoryIndex = match[1];
                    break;
                }
            }
        }

        // If we found the category index, search ONLY its children
        if (categoryIndex !== null) {
            const childRows = root.querySelectorAll(`tr[id*="-vmd-child-${categoryIndex}-"]`);
            for (const childTr of childRows) {
                const childVal = (childTr.getAttribute('data-row') || '').trim().toLowerCase();
                if (childVal === needle || _isSimilar(childVal, needle)) {
                    return childTr;
                }
            }
        }
    }

    // 2. Fallbacks if the strict parent-child match failed
    // First try exact match in flat rows
    const flatRows = root.querySelectorAll('tr[data-row]');
    for (const tr of flatRows) {
        const val = (tr.getAttribute('data-row') || '').trim().toLowerCase();
        // Exact match
        if (val === needle) return tr;
        // Contains match
        if (val.includes(needle) || needle.includes(val)) return tr;
        // Similar match (for slight variations)
        if (_isSimilar(val, needle)) return tr;
    }

    // Try child rows specifically if flat rows didn't match perfectly
    const childRows = root.querySelectorAll('tr[id*="-vmd-child-"]');
    for (const tr of childRows) {
        const childVal = (tr.getAttribute('data-row') || '').trim().toLowerCase();
        if (childVal === needle || _isSimilar(childVal, needle)) {
            return tr;
        }
    }
    // Try to find category rows that match if nothing else did
    const categoryRows = root.querySelectorAll('tr[id*="-vmd-category-"]');
    for (const tr of categoryRows) {
        const catVal = (tr.getAttribute('data-row') || '').trim().toLowerCase();
        if (catVal === needle || _isSimilar(catVal, needle)) {
            return tr;
        }
    }
    return null;
}
// Helper function for fuzzy row matching
function _findRowFuzzy(root, searchValue) {
    const needle = searchValue.toLowerCase();
    const rows = root.querySelectorAll('tr[data-row]');
    for (const tr of rows) {
        const val = (tr.getAttribute('data-row') || '').trim().toLowerCase();
        // Exact match
        if (val === needle) return tr;
        // Contains match
        if (val.includes(needle) || needle.includes(val)) return tr;
        // Similar match (for slight variations)
        if (_isSimilar(val, needle)) return tr;
    }
    return null;
}
// Helper function for fuzzy header matching
function _findHeaderFuzzy(root, searchValue) {
    const needle = searchValue.toLowerCase();
    const headers = root.querySelectorAll('[data-header]');
    for (const header of headers) {
        const val = (header.getAttribute('data-header') || '').trim().toLowerCase();
        // Exact match
        if (val === needle) return header;
        // Contains match - VERY CAREFUL: only if it's a substantive match, not just "n" matching "Total N"
        if (val.includes(needle) && needle.length > 3) return header;
        if (needle.includes(val) && val.length > 3) return header;
        // Similar match (for slight variations)
        if (_isSimilar(val, needle)) return header;
    }
    return null;
}
// Helper function to check if two strings are similar
function _isSimilar(str1, str2) {
    if (str1 === str2) return true;

    // Instead of stripping all spaces right away which concatenates words (e.g. "Total N" -> "totaln"),
    // let's compare word by word first to prevent "totaln" from matching "hospitalizationn".
    const words1 = str1.toLowerCase().replace(/[^\w\s]/g, '').split(/\s+/).filter(w => w.length > 0);
    const words2 = str2.toLowerCase().replace(/[^\w\s]/g, '').split(/\s+/).filter(w => w.length > 0);

    // Check if one is an exact subset of the other (e.g., "Total N" vs "Total N N 207")
    // Only if the smaller string has at least 2 words or is a long word.
    if (words1.length > 0 && words2.length > 0) {
        const smaller = words1.length < words2.length ? words1 : words2;
        const larger = words1.length < words2.length ? words2 : words1;

        let allMatch = true;
        for (const word of smaller) {
            if (!larger.includes(word)) {
                allMatch = false;
                break;
            }
        }
        // If it's a substantive subset match (not just the letter "n")
        if (allMatch && (smaller.length > 1 || smaller[0].length > 3)) {
            return true;
        }

        // Check overlap percentage for longer phrases
        const commonWords = words1.filter(word => words2.includes(word));
        if (commonWords.length >= Math.min(words1.length, words2.length) * 0.7 && commonWords.length > 1) {
            return true;
        }
    }

    // Fallback: Remove common punctuation and spaces, but demand almost exact match
    const clean1 = str1.replace(/[^\w]/g, '').toLowerCase();
    const clean2 = str2.replace(/[^\w]/g, '').toLowerCase();
    if (clean1 === clean2) return true;

    // ONLY allow includes if the strings are exceptionally long, preventing "n" from matching "hospitalizationn"
    if (clean1.length > 8 && clean2.length > 8) {
        if (clean1.includes(clean2) || clean2.includes(clean1)) return true;
    }

    return false;
}
// Helper functions (unchanged)
function _tableEl(side) {
    const root = document.getElementById(side === 'source' ? 'sourceTableDisplay' : 'targetTableDisplay');
    return root ? root.querySelector('table') : null;
}
function _rowCenterYFuzzy(side, rowName, containerRect) {
    const root = document.getElementById(side === 'source' ? 'sourceTableDisplay' : 'targetTableDisplay');
    if (!root) return null;
    const needle = String(rowName || '').trim().toLowerCase();
    const rows = root.querySelectorAll('tr[data-row]');
    console.log(`Fuzzy search for "${needle}" on ${side} side, found ${rows.length} rows`);
    for (const tr of rows) {
        const val = (tr.getAttribute('data-row') || '').trim().toLowerCase();
        console.log(`Comparing "${needle}" with "${val}"`);
        if (val === needle || val.includes(needle) || needle.includes(val)) {
            const r = tr.getBoundingClientRect();
            const centerY = (r.top + r.height / 2) - containerRect.top;
            console.log(`Fuzzy match found: ${val}, centerY=${centerY}`);
            return centerY;
        }
    }
    console.warn(`No fuzzy match found for "${needle}" on ${side} side`);
    return null;
}
function _drawPath(svg, d, stroke, width, opacity) {
    const path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
    path.setAttribute('d', d);
    path.setAttribute('stroke', stroke);
    path.setAttribute('stroke-width', String(width));
    path.setAttribute('stroke-linecap', 'square');
    path.setAttribute('stroke-linejoin', 'miter');
    path.setAttribute('fill', 'none');
    path.setAttribute('opacity', String(opacity));
    svg.appendChild(path);
}
function _drawCircle(svg, cx, cy, r, fill) {
    const circle = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
    circle.setAttribute('cx', cx);
    circle.setAttribute('cy', cy);
    circle.setAttribute('r', r);
    circle.setAttribute('fill', fill);
    circle.setAttribute('opacity', '0.8');
    svg.appendChild(circle);
}
function _drawText(svg, x, y, text, fill, fontSize) {
    const textEl = document.createElementNS('http://www.w3.org/2000/svg', 'text');
    textEl.setAttribute('x', x);
    textEl.setAttribute('y', y);
    textEl.setAttribute('fill', fill);
    textEl.setAttribute('font-size', fontSize);
    textEl.setAttribute('font-family', 'Arial, sans-serif');
    textEl.setAttribute('text-anchor', 'middle');
    textEl.textContent = text;
    svg.appendChild(textEl);
}
// Enhanced mapping display
function displayEnhancedMapping(resultData) {
    var svg = document.getElementById('connectionOverlay');
    if (svg) svg.innerHTML = '';
    // Check if this is a merge operation result
    if (resultData.Merged_Schema && resultData.Merged_Schema.length > 0) {
        displayMergeResults(resultData);
    } else if (window.schemaType === 'complex' || resultData.HMD_matches || resultData.VMD_matches) {
        console.log('📂 Displaying hierarchical mapping for complex schema');
        displayHierarchicalMapping(resultData);
    } else if (resultData.column_matches || resultData.matches) {
        console.log('📂 Displaying simple mapping for relational schema');
        displaySimpleMapping(resultData);
    } else {
        console.log('📂 No matching display condition, defaulting to hierarchical for complex schema');
        if (window.schemaType === 'complex') {
            displayHierarchicalMapping(resultData);
        } else {
            displaySimpleMapping(resultData);
        }
    }
}
function displayHierarchicalMapping(resultData) {
    var sourceContainer = document.getElementById('sourceTableDisplay');
    var targetContainer = document.getElementById('targetTableDisplay');
    var summaryContainer = document.getElementById('mappingSummary');

    // REUSE PREVIEW HTML: Use the backend-rendered HTML instead of re-rendering with JavaScript
    if (sourceData && sourcePreviewHTML) {
        console.log('✅ Reusing source preview HTML for mapping display');
        sourceContainer.innerHTML = sourcePreviewHTML;
        // Apply current "Show Data Values" checkbox state and force color coding
        setTimeout(function () {
            var checkbox = document.getElementById('sourceDataToggle');
            if (checkbox && checkbox.checked) {
                updateTableDataDisplay('sourceTableDisplay', true);
            } else {
                // Force data display with color coding even if checkbox is unchecked
                updateTableDataDisplay('sourceTableDisplay', true);
                if (checkbox) checkbox.checked = true;
            }
        }, 100);
    }
    if (targetData && targetPreviewHTML) {
        console.log('✅ Reusing target preview HTML for mapping display');
        targetContainer.innerHTML = targetPreviewHTML;
        // Apply current "Show Data Values" checkbox state and force color coding
        setTimeout(function () {
            var checkbox = document.getElementById('targetDataToggle');
            if (checkbox && checkbox.checked) {
                updateTableDataDisplay('targetTableDisplay', true);
            } else {
                // Force data display with color coding even if checkbox is unchecked
                updateTableDataDisplay('targetTableDisplay', true);
                if (checkbox) checkbox.checked = true;
            }
        }, 100);
    }
    // NOTE: Do NOT clear mainMergedSchemaDisplay here - it's handled separately
    // by the merged table display code in showResults and tab switch handlers
    var hmdMatches = resultData.HMD_matches || [];
    var vmdMatches = resultData.VMD_matches || [];
    var hmdHTML = '<div style="margin-bottom:12px;">' +
        '<div style="font-weight:bold; color:#2E7D32; margin-bottom:6px;">Horizontal Meta Data - ' + hmdMatches.length + ' matches </div>';
    hmdMatches.forEach(function (m) {
        hmdHTML += '<div style="display:inline-block; padding:4px 8px; margin:3px; border-radius:12px; background:#e8f5e9; color:#1b5e20; border:1px solid #c8e6c9; font-size:13px;">' +
            m.source + ' → ' + m.target +
            '</div>';
    });
    hmdHTML += '</div>';
    var vmdHTML = '<div>' +
        '<div style="font-weight:bold; color:#c62828; margin-bottom:6px;">Vertical Meta Data - ' + vmdMatches.length + ' matches </div>';
    vmdMatches.forEach(function (m) {
        vmdHTML += '<div style="display:inline-block; padding:4px 8px; margin:3px; border-radius:12px; background:#ffebee; color:#b71c1c; border:1px solid #ffcdd2; font-size:13px;">' +
            m.source + ' → ' + m.target +
            '</div>';
    });
    vmdHTML += '</div>';
    summaryContainer.innerHTML = hmdHTML + vmdHTML;
    setTimeout(function () { drawConnectionLines(resultData); }, 100);
    document.getElementById('tableMappingView').style.display = 'block';
}
function displayMergeResults(resultData) {
    var sourceContainer = document.getElementById('sourceTableDisplay');
    var targetContainer = document.getElementById('targetTableDisplay');
    var summaryContainer = document.getElementById('mappingSummary');
    var mergedSchemaSection = document.getElementById('mergedSchemaSection');
    var mainMergedContainer = document.getElementById('mainMergedSchemaDisplay');

    // REUSE PREVIEW HTML: Use the backend-rendered HTML for source/target tables
    if (sourceData && sourcePreviewHTML) {
        console.log('✅ Reusing source preview HTML for merge display');
        sourceContainer.innerHTML = sourcePreviewHTML;
        // Apply current "Show Data Values" checkbox state and force color coding
        setTimeout(function () {
            var checkbox = document.getElementById('sourceDataToggle');
            if (checkbox && checkbox.checked) {
                updateTableDataDisplay('sourceTableDisplay', true);
            } else {
                // Force data display with color coding even if checkbox is unchecked
                updateTableDataDisplay('sourceTableDisplay', true);
                if (checkbox) checkbox.checked = true;
            }
        }, 100);
    }
    if (targetData && targetPreviewHTML) {
        console.log('✅ Reusing target preview HTML for merge display');
        targetContainer.innerHTML = targetPreviewHTML;
        // Apply current "Show Data Values" checkbox state and force color coding
        setTimeout(function () {
            var checkbox = document.getElementById('targetDataToggle');
            if (checkbox && checkbox.checked) {
                updateTableDataDisplay('targetTableDisplay', true);
            } else {
                // Force data display with color coding even if checkbox is unchecked
                updateTableDataDisplay('targetTableDisplay', true);
                if (checkbox) checkbox.checked = true;
            }
        }, 100);
    }
    // Show and populate the merged schema section for merge operations - support both formats
    var hmdMerged = resultData.HMD_Merged_Schema || (resultData.Merged_Schema && resultData.Merged_Schema.HMD_Merged_Schema);
    var vmdMerged = resultData.VMD_Merged_Schema || (resultData.Merged_Schema && resultData.Merged_Schema.VMD_Merged_Schema);
    console.log('📂 Checking merged schema data:', {
        hmdMerged: hmdMerged,
        vmdMerged: vmdMerged,
        resultDataKeys: Object.keys(resultData)
    });
    // Also check for Merged_Data which indicates a merge operation even if schemas aren't present yet
    var mergedData = resultData.Merged_Data;
    var hasMergeOperation = hmdMerged || vmdMerged || mergedData;
    if (hasMergeOperation) {
        console.log('ðŸ—ï¸ Merge operation detected - showing merged schema section');
        if (mergedSchemaSection) {
            mergedSchemaSection.style.display = 'block';
        }
        // Clear and create merged schema table immediately
        if (mainMergedContainer) {
            mainMergedContainer.innerHTML = '';
        }
        var mergedSchemaTable = createMergedSchemaTable(resultData);
        console.log('📊 [MERGED-TABLE] createMergedSchemaTable returned:', Object.keys(mergedSchemaTable), 'Data type:', typeof mergedSchemaTable['MergedTable.Data']);
        if (Object.keys(mergedSchemaTable).length > 0 && mainMergedContainer) {
            console.log('📊 [MERGED-TABLE] Displaying merged schema table in main Schema Mapping tab');
            var mergedHTML = createEnhancedTable(mergedSchemaTable, 'main-merged', null);
            console.log('📊 [MERGED-TABLE] HTML length:', mergedHTML.length, 'first 500 chars:', mergedHTML.substring(0, 500));
            mainMergedContainer.innerHTML = mergedHTML;
            // Apply coloring to merged table like other tables - increase timeout for reliability
            setTimeout(function () {
                var checkbox = document.getElementById('sourceDataToggle');
                var showData = checkbox ? checkbox.checked : true;
                updateTableDataDisplay('mainMergedSchemaDisplay', showData);
                // Apply dashed border styling after table is rendered - add extra delay
                setTimeout(function () {
                    addVerticalDashedLines('mainMergedSchemaDisplay');
                }, 50);
            }, 200);
        } else {
            console.log('[WARNING] Merged schema table is empty, but merge operation detected');
        }
    } else {
        console.log('🚫 No merge operation detected - hiding merged schema section');
        // Hide merged schema section for non-merge operations
        if (mergedSchemaSection) {
            mergedSchemaSection.style.display = 'none';
        }
    }
    // Support both old and new JSON structure formats
    var mergedSchema = resultData.Merged_Schema || [];
    var mergedData = resultData.Merged_Data || [];
    var mapSchema1 = resultData.Map_Schema1 || [];
    var mapSchema2 = resultData.Map_Schema2 || [];
    var summaryHTML = '<div style="text-align: left;">';
    if (mergedSchema.length > 0) {
        summaryHTML += '<div style="margin-bottom: 15px;">';
        summaryHTML += '<h4 style="color: #2E7D32; margin-bottom: 8px;">Merged Schema</h4>';
        summaryHTML += '<div style="background: #e8f5e9; padding: 10px; border-radius: 8px; border: 1px solid #c8e6c9;">';
        mergedSchema.forEach(function (attr) {
            summaryHTML += '<span style="display: inline-block; padding: 4px 8px; margin: 3px; background: white; border-radius: 6px; font-size: 13px; color: #1b5e20;">' + attr + '</span>';
        });
        summaryHTML += '</div></div>';
    }
    if (mapSchema1.length > 0 || mapSchema2.length > 0) {
        summaryHTML += '<div style="margin-bottom: 15px;">';
        summaryHTML += '<h4 style="color: #c62828; margin-bottom: 8px;">Schema Mappings</h4>';
        if (mapSchema1.length > 0) {
            summaryHTML += '<div style="margin-bottom: 10px;"><strong>Source Mappings:</strong></div>';
            mapSchema1.forEach(function (mapping) {
                summaryHTML += '<div style="display: inline-block; padding: 4px 8px; margin: 3px; border-radius: 12px; background: #ffebee; color: #b71c1c; border: 1px solid #ffcdd2; font-size: 13px;">' +
                    mapping.source + ' → ' + mapping.target + '</div>';
            });
        }
        if (mapSchema2.length > 0) {
            summaryHTML += '<div style="margin-bottom: 10px; margin-top: 10px;"><strong>Target Mappings:</strong></div>';
            mapSchema2.forEach(function (mapping) {
                summaryHTML += '<div style="display: inline-block; padding: 4px 8px; margin: 3px; border-radius: 12px; background: #e3f2fd; color: #1565c0; border: 1px solid #bbdefb; font-size: 13px;">' +
                    mapping.source + ' → ' + mapping.target + '</div>';
            });
        }
        summaryHTML += '</div>';
    }
    summaryHTML += '</div>';
    summaryContainer.innerHTML = summaryHTML;
    document.getElementById('tableMappingView').style.display = 'block';
}
function createEnhancedTable(data, type, matchData) {
    console.log('🏗️ createEnhancedTable called with type:', type, 'data keys:', Object.keys(data));
    if (type === 'main-merged') {
        console.log('📊 [MAIN-MERGED] Data structure:', JSON.stringify(Object.keys(data)));
        console.log('📊 [MAIN-MERGED] Data.MergedTable.Data type:', typeof data['MergedTable.Data'], 'isArray:', Array.isArray(data['MergedTable.Data']));
    }
    var html = '<div style="border: 2px solid #333; background: white; overflow: auto; max-height: 70vh; max-width: 100%; position: relative;">';
    var hmdData = null;
    var vmdData = null;
    var vmdHeader = '';
    var tableData = null; // NEW: Store the data array
    Object.entries(data).forEach(function (kv) {
        var key = kv[0], value = kv[1];
        if (key.endsWith('.HMD')) hmdData = value;
        else if (key.endsWith('.VMD')) vmdData = value;
        else if (key.endsWith('.VMD_HEADER') && typeof value === 'string') vmdHeader = value;
        else if (key.endsWith('.Data')) {
            tableData = value; // NEW: Extract data array
            console.log('📊 Found table data for type "' + type + '":', tableData);
        }
    });
    if (!hmdData || !vmdData) return '<p>Invalid table structure</p>';

    // DEBUG: Check if VMD data contains is_vmd_category objects for merged tables
    if (type === 'main-merged' || type === 'merged' || type === 'merged2') {
        var categoryCount = 0;
        if (Array.isArray(vmdData)) {
            vmdData.forEach(function (item, idx) {
                if (typeof item === 'object' && item && item.is_vmd_category === true) {
                    categoryCount++;
                    console.log('📂 [MERGED-VMD] Found is_vmd_category:', item.text, 'with', (item.children || []).length, 'children');
                }
            });
        }
        console.log('📂 [MERGED-VMD] Total VMD items:', vmdData.length, 'Categories:', categoryCount);
    }
    // Store original complete attribute lists for use in merged displays
    if (type === 'source') {
        // Extract all HMD attributes
        window.originalSourceHMD = [];
        if (Array.isArray(hmdData)) {
            hmdData.forEach(function (item, idx) {
                console.log('📋 Source HMD item', idx, ':', item, 'type:', typeof item);
                if (typeof item === 'string') {
                    console.log('📋 Source HMD: Adding string attribute', item);
                    window.originalSourceHMD.push(item);
                } else if (typeof item === 'object' && item) {
                    // Extract attribute from object format
                    var foundAttr = false;
                    for (var key in item) {
                        if (key.startsWith('attribute') && typeof item[key] === 'string') {
                            console.log('📋 Source HMD: Adding attribute', item[key], 'from object:', item);
                            window.originalSourceHMD.push(item[key]);
                            foundAttr = true;
                            break;
                        }
                    }
                    if (!foundAttr) {
                        console.log('[WARNING] Source HMD: No valid attribute found in object:', item);
                    }
                }
            });
        }
        // Extract all VMD attributes
        window.originalSourceVMD = [];
        if (Array.isArray(vmdData)) {
            vmdData.forEach(function (item) {
                if (typeof item === 'string') {
                    window.originalSourceVMD.push(item);
                } else if (typeof item === 'object' && item) {
                    // Extract attribute from object format
                    for (var key in item) {
                        if (key.startsWith('attribute') && typeof item[key] === 'string') {
                            window.originalSourceVMD.push(item[key]);
                            break;
                        }
                    }
                }
            });
        }
        console.log('📋 Stored original source attributes - HMD:', window.originalSourceHMD, 'VMD:', window.originalSourceVMD);
    }
    if (type === 'target') {
        // Extract all HMD attributes  
        window.originalTargetHMD = [];
        if (Array.isArray(hmdData)) {
            hmdData.forEach(function (item, idx) {
                console.log('📋 Target HMD item', idx, ':', item, 'type:', typeof item);
                if (typeof item === 'string') {
                    console.log('📋 Target HMD: Adding string attribute', item);
                    window.originalTargetHMD.push(item);
                } else if (typeof item === 'object' && item) {
                    // Extract attribute from object format
                    var foundAttr = false;
                    for (var key in item) {
                        if (key.startsWith('attribute') && typeof item[key] === 'string') {
                            console.log('📋 Target HMD: Adding attribute', item[key], 'from object:', item);
                            window.originalTargetHMD.push(item[key]);
                            foundAttr = true;
                            break;
                        }
                    }
                    if (!foundAttr) {
                        console.log('[WARNING] Target HMD: No valid attribute found in object:', item);
                    }
                }
            });
        }
        // Extract all VMD attributes
        window.originalTargetVMD = [];
        if (Array.isArray(vmdData)) {
            vmdData.forEach(function (item) {
                if (typeof item === 'string') {
                    window.originalTargetVMD.push(item);
                } else if (typeof item === 'object' && item) {
                    // Extract attribute from object format  
                    for (var key in item) {
                        if (key.startsWith('attribute') && typeof item[key] === 'string') {
                            window.originalTargetVMD.push(item[key]);
                            break;
                        }
                    }
                }
            });
        }
        console.log('📋 Stored original target attributes - HMD:', window.originalTargetHMD, 'VMD:', window.originalTargetVMD);
    }
    // Use compact styling for merged tables, normal styling for source/target
    var tableStyle = (type === 'main-merged' || type === 'merged' || type === 'merged2')
        ? 'border-collapse: collapse; font-size: 18px; font-weight: bold; table-layout: auto; margin: 0 auto; white-space: nowrap;'
        : 'width: 100%; border-collapse: collapse; font-size: 14px; font-weight: bold;';
    html += '<table style="' + tableStyle + '">';
    var headerStructure = analyzeHeaderStructure(hmdData, type);
    html += createHierarchicalHeaders(headerStructure, type, matchData, vmdHeader);
    html += '<tbody>';
    // Enhanced VMD rendering with hierarchy support (JavaScript version)
    html += renderVmdRowsWithHierarchyJS(vmdData, type, matchData, count_columns_from_hmd_fixed(hmdData), tableData, hmdData);
    html += '</tbody></table></div>';
    return html;
}
function count_columns_from_hmd_fixed(hmd_data) {
    if (!hmd_data) {
        return 0;
    }
    let count = 0;
    for (const item of hmd_data) {
        if (typeof item === 'object' && item && item.is_childless) {
            count += item.colspan || 1;
        } else if (typeof item === 'object' && item && item.children && Array.isArray(item.children) && item.children.length > 0) {
            // Parent with children: count each child as a separate column
            count += item.children.length;
        } else {
            count += 1;
        }
    }
    return count;
}
function analyzeHeaderStructure(hmdData, tableType) {
    if (!hmdData || hmdData.length === 0) return { levels: 1, structure: [] };
    console.log('📂 analyzeHeaderStructure called with hmdData:', hmdData, 'tableType:', tableType);
    // Use original simple logic for source/target tables, new logic only for merged tables
    if (tableType && (tableType === 'main-merged' || tableType === 'merged' || tableType === 'merged2')) {
        return analyzeHeaderStructureForMerged(hmdData, tableType);
    }
    // Original simple logic for source/target tables
    var stringHeaders = [];
    var objectHeaders = [];
    // Simple processing - just categorize items as they are
    hmdData.forEach(function (item) {
        if (typeof item === 'string') {
            stringHeaders.push(item);
        } else if (typeof item === 'object' && item && item.is_childless) {
            objectHeaders.push(item);
        } else if (typeof item === 'object' && item) {
            // Handle objects with attribute keys (e.g., attribute1, attribute2, etc.)
            var attributeValue = null;
            for (var key in item) {
                if (key.startsWith('attribute') && typeof item[key] === 'string') {
                    attributeValue = item[key];
                    break;
                }
            }
            if (attributeValue) {
                // Check if it has children for hierarchical processing
                if (item.children && Array.isArray(item.children) && item.children.length > 0) {
                    // Extract child values and create hierarchical headers
                    item.children.forEach(function (child) {
                        for (var childKey in child) {
                            if (childKey.startsWith('child_level1.') && typeof child[childKey] === 'string') {
                                stringHeaders.push(attributeValue + '.' + child[childKey]);
                            }
                        }
                    });
                } else {
                    // Simple attribute without children
                    stringHeaders.push(attributeValue);
                }
            } else {
                console.log('🤔 Unhandled item in source/target table:', item);
            }
        }
    });
    var hasHierarchy = stringHeaders.some(function (header) {
        return header.indexOf('.') !== -1;
    });
    if (!hasHierarchy) {
        var structure = [];
        stringHeaders.forEach(function (item) {
            structure.push({ text: item, colspan: 1, level: 0, type: 'normal' });
        });
        objectHeaders.forEach(function (item) {
            structure.push({
                text: item.text,
                colspan: item.colspan || 1,
                level: 0,
                type: 'childless'
            });
        });
        console.log('🔍 Returning flat structure for source/target:', { levels: 1, structure: structure, objectHeaders: objectHeaders });
        return { levels: 1, structure: structure, objectHeaders: objectHeaders };
    }
    // For source/target tables with hierarchy, use simpler processing 
    var hierarchy = {};
    var maxLevels = 1;
    stringHeaders.forEach(function (header) {
        var parts = header.split('.');
        maxLevels = Math.max(maxLevels, parts.length);
        var current = hierarchy;
        parts.forEach(function (part, index) {
            if (!current[part]) {
                current[part] = { level: index, children: {} };
            }
            current = current[part].children;
        });
    });
    objectHeaders.forEach(function (item) {
        item.rowspan = maxLevels;
        item.is_childless = true;
    });
    return {
        levels: maxLevels,
        structure: hierarchy,
        objectHeaders: objectHeaders
    };
}
function analyzeHeaderStructureForMerged(hmdData, tableType) {
    console.log('📂¥ Using MERGED table header analysis for:', tableType);
    var stringHeaders = [];
    var objectHeaders = [];
    // Complex logic for merged tables only
    hmdData.forEach(function (item) {
        if (typeof item === 'string') {
            stringHeaders.push(item);
        } else if (typeof item === 'object' && item && item.is_childless) {
            objectHeaders.push(item);
        } else if (typeof item === 'object' && item) {
            var attributeValue = null;
            // Extract attribute value from any attributeX key
            for (var key in item) {
                if (key.startsWith('attribute') && typeof item[key] === 'string') {
                    attributeValue = item[key];
                    break;
                }
            }
            if (attributeValue !== null) {
                if (item.children && Array.isArray(item.children) && item.children.length > 0) {
                    item.children.forEach(function (child) {
                        var cVal = (function (c) { if (!c) return ''; if (typeof c === 'string') return c; for (var k in c) { if ((k.indexOf('attribute') !== -1 || k.indexOf('child_level') !== -1) && typeof c[k] === 'string') return c[k]; } return ''; })(child);
                        if (cVal) {
                            stringHeaders.push(attributeValue + '.' + cVal);
                        }
                    });
                } else if (attributeValue.indexOf('.') !== -1) {
                    stringHeaders.push(attributeValue);
                } else {
                    stringHeaders.push(attributeValue);
                }
            }
        }
    });
    var hasHierarchy = stringHeaders.some(function (header) {
        return header.indexOf('.') !== -1;
    });
    if (!hasHierarchy) {
        var structure = [];
        stringHeaders.forEach(function (item) {
            structure.push({ text: item, colspan: 1, level: 0, type: 'normal' });
        });
        objectHeaders.forEach(function (item) {
            structure.push({
                text: item.text,
                colspan: item.colspan || 1,
                level: 0,
                type: 'childless'
            });
        });
        return { levels: 1, structure: structure, objectHeaders: objectHeaders };
    }
    // MAINTAIN ORIGINAL ORDER - track positions of all headers
    var orderedHeaders = [];
    // Process each header in original order from stringHeaders, maintaining position
    for (var i = 0; i < stringHeaders.length; i++) {
        var header = stringHeaders[i];
        if (header.indexOf('.') === -1) {
            // Simple string without hierarchy - add as childless object but in correct position
            orderedHeaders.push({
                originalIndex: i,
                type: 'simple',
                text: header,
                is_childless: true
            });
        } else {
            // Hierarchical string - keep for hierarchy processing
            orderedHeaders.push({
                originalIndex: i,
                type: 'hierarchical',
                text: header
            });
        }
    }
    // Filter only hierarchical strings for hierarchy processing, but maintain reference to order
    var hierarchicalStrings = stringHeaders.filter(function (header) {
        return header.indexOf('.') !== -1; // Hierarchical strings with dots
    });
    // Continue processing with only hierarchical strings
    stringHeaders = hierarchicalStrings;
    var hierarchy = {};
    var maxLevels = 1;
    stringHeaders.forEach(function (header) {
        var parts = header.split('.');
        maxLevels = Math.max(maxLevels, parts.length);
        var current = hierarchy;
        parts.forEach(function (part, index) {
            if (!current[part]) {
                current[part] = { children: {}, childOrder: [], level: index };
            }
            // Track child insertion order in parent's childOrder array
            if (index < parts.length - 1) {
                var nextPart = parts[index + 1];
                var parentNode = current[part];
                if (parentNode.childOrder.indexOf(nextPart) === -1) {
                    parentNode.childOrder.push(nextPart);
                }
            }
            current = current[part].children;
        });
    });
    // Build final structure in ORIGINAL ORDER using orderedHeaders
    var finalStructure = {};
    var finalObjectHeaders = [];
    // Sort orderedHeaders by original index to maintain correct order
    orderedHeaders.sort(function (a, b) { return a.originalIndex - b.originalIndex; });
    // Process each item in original order
    for (var i = 0; i < orderedHeaders.length; i++) {
        var item = orderedHeaders[i];
        if (item.type === 'simple') {
            // Simple item - add to objectHeaders but track position
            finalObjectHeaders.push({
                text: item.text,
                colspan: 1,
                rowspan: maxLevels,
                is_childless: true,
                originalIndex: item.originalIndex,
                type: 'simple_in_hierarchy'
            });
        } else if (item.type === 'hierarchical') {
            // Hierarchical item - add to main structure
            var parts = item.text.split('.');
            var parent = parts[0];
            if (hierarchy[parent]) {
                // Use the hierarchy structure built earlier
                finalStructure[parent] = hierarchy[parent];
            }
        }
    }
    // Sort objectHeaders by original position
    finalObjectHeaders.sort(function (a, b) { return a.originalIndex - b.originalIndex; });

    // Build structureOrder from orderedHeaders to track top-level parent order
    var structureOrder = [];
    for (var i = 0; i < orderedHeaders.length; i++) {
        var oh = orderedHeaders[i];
        if (oh.type === 'hierarchical') {
            var parent = oh.text.split('.')[0];
            if (structureOrder.indexOf(parent) === -1) {
                structureOrder.push(parent);
            }
        }
    }
    // Add _childOrder to finalStructure for top-level iteration order
    finalStructure._childOrder = structureOrder;

    console.log('🔍 Returning hierarchical structure:', {
        levels: maxLevels,
        structure: finalStructure,
        objectHeaders: finalObjectHeaders,
        orderedHeaders: orderedHeaders // Include for debugging
    });
    return {
        levels: maxLevels,
        structure: finalStructure,
        objectHeaders: finalObjectHeaders,
        orderedHeaders: orderedHeaders
    };
}
function createHierarchicalHeaders(headerStructure, type, matchData, vmdHeaderLabel) {
    var label = (vmdHeaderLabel || "").trim();
    var html = '<thead>';
    if (headerStructure.levels === 1) {
        html += '<tr>';
        var headerPadding = (type === 'main-merged' || type === 'merged' || type === 'merged2') ? '4px 8px' : '4px';
        var vmdWidth = (type === 'main-merged' || type === 'merged' || type === 'merged2') ? 'white-space: nowrap; ' : '';
        html += '<th class="vmd-header" style="border:1px solid #333;padding:' + headerPadding + ';background:#2E7D32;color:white;text-align:left;' + vmdWidth + '">' + label + '</th>';
        headerStructure.structure.forEach(function (header) {
            var isMatched = isHeaderMatched(header.text, matchData);
            var bgColor = isMatched ? '#c8e6c9' : '#2E7D32';
            var colspan = header.colspan || 1;
            var columnWidth = (type === 'main-merged' || type === 'merged' || type === 'merged2') ? 'white-space: nowrap; ' : '';
            html += '<th style="border:1px solid #333;padding:' + headerPadding + ';background:' + bgColor + ';color:white;text-align:center;' + columnWidth + '" ';
            if (colspan > 1) {
                html += 'colspan="' + colspan + '" ';
            }
            html += 'data-header="' + header.text + '">' + header.text + '</th>';
        });
        html += '</tr>';
        // Add t1/t2 sub-header row for merged tables only
        if (type === 'main-merged' || type === 'merged' || type === 'merged2') {
            html += '<tr class="t1-t2-subheader">';
            // Empty cell for VMD column
            html += '<th style="border:1px solid #333;padding:2px 8px;background:#f5f5f5;color:#333;text-align:center;font-size:12px;"></th>';
            // Add t1/t2 labels for each HMD column
            headerStructure.structure.forEach(function (header) {
                var colspan = header.colspan || 1;
                html += '<th style="border:1px solid #333;padding:2px 8px;background:#f5f5f5;color:#333;text-align:center;font-size:12px;position:relative;" ';
                if (colspan > 1) {
                    html += 'colspan="' + colspan + '" ';
                }
                html += '>';
                // Create t1/t2 layout with dashed separator between them
                html += '<div style="display:flex;justify-content:space-around;align-items:center;padding:0 8px;">';
                html += '<span style="font-weight:bold;color:#8B4513;font-size:18px;flex:1;text-align:center;border-right:2px dashed #666;padding-right:8px;margin-right:8px;">t1</span>';
                html += '<span style="font-weight:bold;color:#800080;font-size:18px;flex:1;text-align:center;">t2</span>';
                html += '</div>';
                html += '</th>';
            });
            html += '</tr>';
        }
    } else {
        html += '<tr>';
        var headerPadding = (type === 'main-merged' || type === 'merged' || type === 'merged2') ? '4px 8px' : '4px';
        var vmdWidth = (type === 'main-merged' || type === 'merged' || type === 'merged2') ? 'white-space: nowrap; ' : '';
        html += '<th class="vmd-header" rowspan="' + headerStructure.levels + '" style="border:1px solid #333;padding:' + headerPadding + ';background:#2E7D32;color:white;text-align:left;' + vmdWidth + '">' + label + '</th>';
        // MODIFIED: Render headers in original order by interleaving structure and objectHeaders
        if (headerStructure.orderedHeaders) {
            // Keep track of rendered hierarchical parents to avoid duplication
            var renderedParents = new Set();

            // Use original order from orderedHeaders to render both hierarchical and simple headers
            for (var i = 0; i < headerStructure.orderedHeaders.length; i++) {
                var orderedItem = headerStructure.orderedHeaders[i];
                if (orderedItem.type === 'simple') {
                    // Find this simple item in objectHeaders and render it
                    var objHeader = headerStructure.objectHeaders.find(function (oh) {
                        return oh.text === orderedItem.text;
                    });
                    if (objHeader) {
                        var columnWidth = (type === 'main-merged' || type === 'merged' || type === 'merged2') ? 'white-space: nowrap; ' : '';
                        html += '<th style="border:1px solid #333;padding:' + headerPadding + ';background:#2E7D32;color:white;text-align:center;' + columnWidth + '" ';
                        html += 'rowspan="' + (objHeader.rowspan || headerStructure.levels) + '" ';
                        html += 'data-header="' + objHeader.text + '">' + objHeader.text + '</th>';
                    }
                } else if (orderedItem.type === 'hierarchical') {
                    // Find this hierarchical item in structure and render it
                    var parts = orderedItem.text.split('.');
                    var parent = parts[0];

                    // Only render if not already rendered
                    if (!renderedParents.has(parent)) {
                        if (headerStructure.structure[parent]) {
                            html += createHeaderRowForLevel({ [parent]: headerStructure.structure[parent] }, 0, headerStructure.levels, '', type, matchData);
                            renderedParents.add(parent);
                        }
                    }
                }
            }
        } else {
            // Fallback to original logic if orderedHeaders not available (for source/target tables)
            console.log('📂§ Using fallback header rendering for table type:', type);
            console.log('📊 Header structure:', headerStructure);
            html += createHeaderRowForLevel(headerStructure.structure, 0, headerStructure.levels, '', type, matchData);
            if (headerStructure.objectHeaders) {
                console.log('ðŸ·ï¸ Rendering objectHeaders:', headerStructure.objectHeaders);
                headerStructure.objectHeaders.forEach(function (item) {
                    var columnWidth = (type === 'main-merged' || type === 'merged' || type === 'merged2') ? 'white-space: nowrap; ' : '';
                    html += '<th style="border:1px solid #333;padding:' + headerPadding + ';background:#2E7D32;color:white;text-align:center;' + columnWidth + '" ';
                    html += 'rowspan="' + (item.rowspan || headerStructure.levels) + '" ';
                    html += 'data-header="' + item.text + '">' + item.text + '</th>';
                });
            } else {
                console.log('âŒ No objectHeaders found in fallback mode');
            }
        }
        html += '</tr>';
        for (var level = 1; level < headerStructure.levels; level++) {
            html += '<tr>';
            html += createHeaderRowForLevel(headerStructure.structure, level, headerStructure.levels, '', type, matchData);
            html += '</tr>';
        }
        // Add t1/t2 sub-header row for merged tables with hierarchical headers
        if (type === 'main-merged' || type === 'merged' || type === 'merged2') {
            console.log('[AUTO] Creating t1/t2 sub-header for type:', type);
            console.log('[AUTO] HeaderStructure.hmdData:', headerStructure.hmdData);
            html += '<tr class="t1-t2-subheader">';
            // Empty cell for VMD column  
            html += '<th style="border:1px solid #333;padding:2px 8px;background:#f5f5f5;color:#333;text-align:center;font-size:12px;"></th>';
            // Calculate total columns and add t1/t2 labels for each data column
            // For merged tables, use the orderedHeaders from the structure instead
            var totalCols;
            if (headerStructure.orderedHeaders && headerStructure.orderedHeaders.length > 0) {
                totalCols = headerStructure.orderedHeaders.length;
                console.log('[AUTO] Using orderedHeaders for column count:', totalCols, headerStructure.orderedHeaders);
            } else {
                totalCols = count_columns_from_hmd_fixed(headerStructure.hmdData || []);
                console.log('[AUTO] Using count_columns_from_hmd_fixed for column count:', totalCols);
            }
            for (var i = 0; i < totalCols; i++) {
                console.log('[AUTO] Adding t1/t2 cell', i + 1, 'of', totalCols);
                html += '<th style="border:1px solid #333;padding:2px 8px;background:#f5f5f5;color:#333;text-align:center;font-size:12px;position:relative;">';
                // Create t1/t2 layout with dashed separator between them
                html += '<div style="display:flex;justify-content:space-around;align-items:center;padding:0 8px;">';
                html += '<span style="font-weight:bold;color:#8B4513;font-size:16px;flex:1;text-align:center;border-right:2px dashed #666;padding-right:8px;margin-right:8px;">t1</span>';
                html += '<span style="font-weight:bold;color:#800080;font-size:16px;flex:1;text-align:center;">t2</span>';
                html += '</div>';
                html += '</th>';
            }
            html += '</tr>';
            console.log('[AUTO] t1/t2 sub-header row completed');
        } else {
            console.log('[AUTO] No t1/t2 sub-header for type:', type);
        }
    }
    html += '</thead>';
    return html;
}
function createHeaderRowForLevel(structure, targetLevel, maxLevels, prefix, type, matchData) {
    var html = '';
    // Use childOrder if available to preserve insertion order, otherwise fall back to Object.entries
    var keys = [];
    if (structure._childOrder && Array.isArray(structure._childOrder)) {
        keys = structure._childOrder;
    } else {
        keys = Object.keys(structure).filter(function (k) { return k !== '_childOrder'; });
    }

    keys.forEach(function (key) {
        var value = structure[key];
        if (!value) return;
        var fullPath = prefix ? (prefix + '.' + key) : key;
        if (value.level === targetLevel) {
            var colspan = calculateColspan(value.children, value.childOrder, maxLevels - targetLevel - 1);
            var isMatched = isHeaderMatched(fullPath, matchData);
            var bgColor = getHeaderColor(targetLevel, isMatched);
            var headerPadding = (type === 'main-merged' || type === 'merged' || type === 'merged2') ? '4px 8px' : '4px';
            var columnWidth = (type === 'main-merged' || type === 'merged' || type === 'merged2') ? 'white-space: nowrap; ' : '';
            html += '<th style="border: 1px solid #333; padding: ' + headerPadding + '; background: ' + bgColor + '; text-align: center; ' + columnWidth + '" colspan="' + colspan + '" data-header="' + fullPath + '">' + key + '</th>';
        }
        // Pass childOrder to recursive calls
        if (value.childOrder && value.childOrder.length > 0) {
            var orderedChildren = { _childOrder: value.childOrder };
            value.childOrder.forEach(function (childKey) {
                orderedChildren[childKey] = value.children[childKey];
            });
            html += createHeaderRowForLevel(orderedChildren, targetLevel, maxLevels, fullPath, type, matchData);
        } else if (Object.keys(value.children).length > 0) {
            html += createHeaderRowForLevel(value.children, targetLevel, maxLevels, fullPath, type, matchData);
        }
    });
    return html;
}
function calculateColspan(children, childOrder, remainingLevels) {
    if (remainingLevels === 0 || Object.keys(children).length === 0) return 1;
    var total = 0;
    // Use childOrder if available to iterate in correct order
    var keys = (childOrder && Array.isArray(childOrder) && childOrder.length > 0) ? childOrder : Object.keys(children);
    keys.forEach(function (key) {
        var child = children[key];
        if (child) {
            total += calculateColspan(child.children, child.childOrder, remainingLevels - 1);
        }
    });
    return Math.max(1, total);
}
function getHeaderColor(level, isMatched) {
    if (isMatched) {
        var colors = ['#c8e6c9', '#a5d6a7', '#81c784'];
        return colors[level] || '#e8f5e8';
    } else {
        var colors2 = ['#2E7D32', '#4CAF50', '#81C784'];
        return colors2[level] || '#2E7D32';
    }
}
function isHeaderMatched(headerText, matchData) {
    if (!matchData || !Array.isArray(matchData.HMD_matches)) return false;
    const h = _normalizeLabel(headerText);
    return matchData.HMD_matches.some(m =>
        _normalizeLabel(m.source) === h || _normalizeLabel(m.target) === h
    );
}
function isRowMatched(rowName, matchData) {
    if (!matchData || !Array.isArray(matchData.VMD_matches)) return false;
    const r = _normalizeLabel(rowName);
    return matchData.VMD_matches.some(m =>
        _normalizeLabel(m.source) === r || _normalizeLabel(m.target) === r
    );
}
function _normalizeLabel(s) {
    return String(s || '').trim().replace(/\s+/g, ' ').toLowerCase();
}
function renderVmdRowsWithHierarchyJS(vmdData, type, matchData, columnCount, tableData, hmdData) {
    console.log('🔍 renderVmdRowsWithHierarchyJS called with:', {
        vmdDataLength: vmdData ? vmdData.length : 0,
        vmdDataType: typeof vmdData,
        vmdDataSample: vmdData ? vmdData.slice(0, 3) : null,
        type: type,
        columnCount: columnCount
    });
    if (!vmdData || vmdData.length === 0) {
        console.log('⚠️ VMD data is empty or null - returning empty string');
        return '';
    }

    // CRITICAL FIX: Normalize VMD data to handle multiple formats:
    // 1. String arrays: ['Age, mean±SD,y', 'Hypertension']
    // 2. Object arrays with children: [{attribute1: "Age", children: []}, ...]
    // 3. is_vmd_category objects: [{is_vmd_category: true, text: "Parent", children: [...]}]
    var normalizedVmdData = [];
    vmdData.forEach(function (item) {
        if (typeof item === 'string') {
            // Already a string - use as is
            normalizedVmdData.push(item);
        } else if (typeof item === 'object' && item) {
            // FIRST: Check if this is already an is_vmd_category object - preserve it
            if (item.is_vmd_category === true) {
                console.log('✅ Preserving is_vmd_category object:', item.text);
                normalizedVmdData.push(item);
            } else {
                // Extract attribute value from object
                var attributeValue = null;
                for (var key in item) {
                    if (key.startsWith('attribute') && typeof item[key] === 'string') {
                        attributeValue = item[key];
                        break;
                    }
                }
                if (attributeValue) {
                    // Check if it has children for hierarchical structure
                    if (item.children && Array.isArray(item.children) && item.children.length > 0) {
                        // Create is_vmd_category object for hierarchical rendering
                        var children = [];
                        item.children.forEach(function (child) {
                            for (var childKey in child) {
                                if (childKey.startsWith('child_level1.') && typeof child[childKey] === 'string') {
                                    children.push(child[childKey]);
                                }
                            }
                        });
                        normalizedVmdData.push({
                            is_vmd_category: true,
                            text: attributeValue,
                            children: children
                        });
                    } else {
                        // Simple string attribute
                        normalizedVmdData.push(attributeValue);
                    }
                }
            }
        }
    });

    console.log('✅ Normalized VMD data:', normalizedVmdData);
    vmdData = normalizedVmdData; // Use normalized data for rendering
    // Extract ordered HMD column headers - MUST match EXACT order from analyzeHeaderStructure
    function getOrderedHMDHeaders(hmdData, tableData) {
        var headers = [];
        if (!hmdData || !tableData) return headers;
        // Use ONLY HMD_Merged_Schema data - extract attributes in order
        var stringHeaders = [];
        var objectHeaders = [];
        // Extract attributes directly from HMD_Merged_Schema in order, handling both hierarchy formats
        for (var i = 0; i < hmdData.length; i++) {
            var item = hmdData[i];
            if (typeof item === 'string') {
                headers.push(item);
            } else if (typeof item === 'object' && item) {
                var attributeValue = null;
                // Extract attribute value from any attributeX key
                for (var key in item) {
                    if (key.startsWith('attribute') && typeof item[key] === 'string') {
                        attributeValue = item[key];
                        break;
                    }
                }
                if (attributeValue) { // Only process if valid attribute found
                    // Handle LLM hierarchy format with children array
                    if (item.children && Array.isArray(item.children) && item.children.length > 0) {
                        item.children.forEach(function (child) {
                            var cVal = (function (c) { if (!c) return ''; if (typeof c === 'string') return c; for (var k in c) { if ((k.indexOf('attribute') !== -1 || k.indexOf('child_level') !== -1) && typeof c[k] === 'string') return c[k]; } return ''; })(child);
                            if (cVal) {
                                headers.push(attributeValue + '.' + cVal);
                            }
                        });
                    } else {
                        // Handle both dot-notation format and simple attributes
                        headers.push(attributeValue);
                    }
                } // End of attributeValue check
            }
        }
        console.log('[OK] Using HMD_Merged_Schema order for headers:', headers);
        return headers;
    }
    var hmdHeaders = getOrderedHMDHeaders(hmdData, tableData);
    console.log('📂 Extracted HMD headers for cell population:', hmdHeaders);
    console.log('📊 Table data received in renderVmdRowsWithHierarchyJS:', tableData);
    console.log('ðŸ—ï¸ HMD data structure used for table headers:', JSON.stringify(hmdData, null, 2));
    console.log('📊 Table data type:', typeof tableData);
    var html = '';
    var skipNext = new Set(); // Track which items to skip (children already rendered)
    var dataRowIndex = 0; // Track position in data array
    console.log('🏁 Starting VMD render loop with dataRowIndex: 0');
    for (var index = 0; index < vmdData.length; index++) {
        if (skipNext.has(index)) {
            continue;
        }
        var item = vmdData[index];
        if (typeof item === 'object' && item !== null && item.is_vmd_category) {
            // This is a hierarchical category with children
            var categoryText = item.text;
            var children = item.children || [];
            // Render category row first
            var isMatched = isRowMatched(categoryText, matchData);
            var rowClass = isMatched ? 'matched-row' : '';
            var rowId = type + '-vmd-category-' + index;
            html += '<tr class="' + rowClass + '" id="' + rowId + '" data-row="' + categoryText + '">';
            // Category cell styling - bold and clean
            var bgColor = 'white';
            var escapedName = (categoryText || '').replace(/"/g, '&quot;');
            var cellPadding = (type === 'main-merged' || type === 'merged' || type === 'merged2') ? '4px 8px' : '4px';
            var vmdCellWidth = (type === 'main-merged' || type === 'merged' || type === 'merged2') ? 'white-space: nowrap; ' : '';
            html += '<td class="vmd-cell" style="border: 1px solid #333; padding: ' + cellPadding + '; text-align: left; font-weight: bold; background: ' + bgColor + '; ' + vmdCellWidth + '">';
            html += '<span class="row-label" data-row-label="' + escapedName + '">' + categoryText + '</span>';
            html += '</td>';
            // Category row - no data (empty cells)
            for (var i = 0; i < columnCount; i++) {
                var dataCellWidth = (type === 'main-merged' || type === 'merged' || type === 'merged2') ? 'width: auto; min-width: 120px; max-width: none; white-space: nowrap; padding: 8px 12px; ' : '';
                html += '<td style="border: 1px solid #333; padding: ' + cellPadding + '; background: white; text-align: center; font-weight: bold; ' + dataCellWidth + '" data-cell-value=""></td>';
            }
            html += '</tr>';

            console.log('📝 Rendered Category:', categoryText, 'consuming Index', dataRowIndex);

            // AUTOMATIC ADJUSTMENT: Check if current data row is empty (placeholder for category)
            // If it has data, assume it belongs to the child and DO NOT consume it.
            var shouldConsumeRow = true;
            if (tableData && Array.isArray(tableData) && dataRowIndex < tableData.length) {
                var currentRow = tableData[dataRowIndex];
                // Check if row has any non-empty values
                var hasData = Array.isArray(currentRow) && currentRow.some(function (cell) {
                    return cell && cell !== '' && cell !== '-' && cell !== '—';
                });

                if (hasData) {
                    console.log('⚠️ Category row appears to have data -> Skipping increment (Assuming data belongs to child):', currentRow);
                    shouldConsumeRow = false;
                } else {
                    console.log('✅ Category row is empty -> Consuming index');
                }
            }

            if (shouldConsumeRow) {
                dataRowIndex++; // Skip the empty data row for category
            }
            // Render children as separate rows with slight indentation
            for (var childIndex = 0; childIndex < children.length; childIndex++) {
                var child = children[childIndex];
                var childMatched = isRowMatched(child, matchData);
                var childRowClass = childMatched ? 'matched-row' : '';
                var childRowId = type + '-vmd-child-' + index + '-' + childIndex;
                html += '<tr class="' + childRowClass + '" id="' + childRowId + '" data-row="' + child + '">';
                // Child cell with slight indentation
                var childBg = 'white';
                var escapedChild = (child || '').replace(/"/g, '&quot;');
                var childPadding = (type === 'main-merged' || type === 'merged' || type === 'merged2') ? '4px 8px 4px 10px' : '4px 4px 4px 12px';
                var vmdCellWidth = (type === 'main-merged' || type === 'merged' || type === 'merged2') ? 'white-space: nowrap; ' : '';
                html += '<td class="vmd-cell" style="border: 1px solid #333; padding: ' + childPadding + '; text-align: left; font-weight: normal; background: ' + childBg + '; ' + vmdCellWidth + '">';
                html += '<span class="row-label" data-row-label="' + escapedChild + '">' + child + '</span>';
                html += '</td>';
                // Child data cells
                for (var i = 0; i < columnCount; i++) {
                    var cellValue = '';
                    // Use merged data structure if available, fallback to original array format
                    if (tableData && typeof tableData === 'object' && !Array.isArray(tableData)) {
                        // New merged data format: { "VMD_ROW": { "HMD_COL": "t1 | t2" } }
                        var rowData = tableData[child];
                        if (rowData && i < hmdHeaders.length) {
                            var hmdHeader = hmdHeaders[i];
                            cellValue = rowData[hmdHeader] || '';
                            console.log('📂 Looking up hierarchical cell data:', {
                                child: child,
                                columnIndex: i,
                                hmdHeader: hmdHeader,
                                cellValue: cellValue,
                                availableDataKeys: Object.keys(rowData),
                                allHmdHeaders: hmdHeaders
                            });
                        }
                    } else if (tableData && Array.isArray(tableData) && dataRowIndex < tableData.length) {
                        // Original array format
                        var rowData = tableData[dataRowIndex];
                        if (Array.isArray(rowData) && i < rowData.length) {
                            cellValue = rowData[i] || '';
                        }
                    }
                    var dataCellWidth = (type === 'main-merged' || type === 'merged' || type === 'merged2') ? 'width: auto; min-width: 120px; max-width: none; white-space: nowrap; padding: 8px 12px; ' : '';
                    // Apply color formatting and handle pipe separators
                    var displayValue = cellValue;
                    if (type === 'main-merged' || type === 'merged' || type === 'merged2') {
                        // For main merged table, remove pipe and format with colors side by side
                        if (cellValue && cellValue.includes(' | ')) {
                            var parts = cellValue.split(' | ');
                            var t1Value = parts[0] && parts[0] !== '-' ? parts[0] : '';
                            var t2Value = parts[1] && parts[1] !== '-' ? parts[1] : '';
                            var t1Formatted = t1Value ? '<span style="color: #8B4513; font-weight: bold;">' + t1Value + '</span>' : '-';
                            var t2Formatted = t2Value ? '<span style="color: #800080; font-weight: bold;">' + t2Value + '</span>' : '-';
                            // Display with internal dashed separator
                            displayValue = '<div class="merged-cell-separator" style="position: relative;">' +
                                '<div class="cell-data">' + t1Formatted + '</div>' +
                                '<div class="cell-data">' + t2Formatted + '</div>' +
                                '</div>';
                        }
                    } else if (type === 'source-from-merged' || type === 'target-from-merged' || type === 'source' || type === 'target') {
                        if (cellValue && cellValue.includes(' | ')) {
                            var parts = cellValue.split(' | ');
                            var t1Value = parts[0] && parts[0] !== '-' ? parts[0] : '';
                            var t2Value = parts[1] && parts[1] !== '-' ? parts[1] : '';
                            if (type === 'source-from-merged' || type === 'source') {
                                // For source table, show t1 in brown and t2 faded/hidden
                                var t1Formatted = t1Value ? '<span style="color: #8B4513; font-weight: bold;">' + t1Value + '</span>' : '-';
                                displayValue = t1Formatted;
                            } else if (type === 'target-from-merged' || type === 'target') {
                                // For target table, show t2 in purple and t1 faded/hidden
                                var t2Formatted = t2Value ? '<span style="color: #800080; font-weight: bold;">' + t2Value + '</span>' : '-';
                                displayValue = t2Formatted;
                            }
                        } else if (cellValue && cellValue !== '' && cellValue !== '-') {
                            // If no pipe separator but has value, apply appropriate color based on table type
                            if (type === 'source-from-merged' || type === 'source') {
                                displayValue = '<span style="color: #8B4513; font-weight: bold;">' + cellValue + '</span>';
                            } else if (type === 'target-from-merged' || type === 'target') {
                                displayValue = '<span style="color: #800080; font-weight: bold;">' + cellValue + '</span>';
                            }
                        }
                    }
                    html += '<td style="border: 1px solid #333; padding: ' + cellPadding + '; background: white; text-align: center; font-weight: bold; ' + dataCellWidth + '">' + displayValue + '</td>';
                }
                html += '</tr>';
                console.log('📝 Rendered Child:', child, 'consuming Index', dataRowIndex);
                dataRowIndex++; // Move to next data row for next child
            }
        }
        else if (typeof item === 'string') {
            // Handle both flat items and hierarchical paths
            if (item.indexOf('.') !== -1) {
                // This might be a hierarchical path like "Category.Child"
                var parts = item.split('.', 2);
                if (parts.length === 2) {
                    // Check if this is already handled by a category above
                    var parentCategory = parts[0];
                    var childName = parts[1];
                    // Look for parent category in previous items
                    var foundParent = false;
                    for (var prevIndex = 0; prevIndex < index; prevIndex++) {
                        var prevItem = vmdData[prevIndex];
                        if (typeof prevItem === 'object' &&
                            prevItem !== null &&
                            prevItem.is_vmd_category &&
                            prevItem.text === parentCategory) {
                            foundParent = true;
                            break;
                        }
                    }
                    if (foundParent) {
                        // This child is already rendered under its parent category
                        continue;
                    }
                }
            }
            // Render as flat item
            var isMatched = isRowMatched(item, matchData);
            var rowClass = isMatched ? 'matched-row' : '';
            var rowId = type + '-vmd-' + index;
            html += '<tr class="' + rowClass + '" id="' + rowId + '" data-row="' + item + '">';
            var bgColor = 'white';
            var escapedName = (item || '').replace(/"/g, '&quot;');
            var cellPadding = (type === 'main-merged' || type === 'merged' || type === 'merged2') ? '4px 8px' : '4px';
            var vmdCellWidth = (type === 'main-merged' || type === 'merged' || type === 'merged2') ? 'white-space: nowrap; ' : '';
            html += '<td class="vmd-cell" style="border: 1px solid #333; padding: ' + cellPadding + '; text-align: left; font-weight: bold; background: ' + bgColor + '; ' + vmdCellWidth + '">';
            html += '<span class="row-label" data-row-label="' + escapedName + '">' + item + '</span>';
            html += '</td>';
            // Add data cells
            for (var i = 0; i < columnCount; i++) {
                var cellValue = '';
                // Use merged data structure if available, fallback to original array format
                if (tableData && typeof tableData === 'object' && !Array.isArray(tableData)) {
                    // New merged data format: { "VMD_ROW": { "HMD_COL": "t1 | t2" } }
                    var rowData = tableData[item];
                    if (rowData && i < hmdHeaders.length) {
                        var hmdHeader = hmdHeaders[i];
                        cellValue = rowData[hmdHeader] || '';
                        console.log('📂 Looking up flat cell data:', { item, hmdHeader, cellValue, rowData, columnIndex: i });
                    }
                } else if (tableData && Array.isArray(tableData) && dataRowIndex < tableData.length) {
                    // Original array format
                    var rowData = tableData[dataRowIndex];
                    if (Array.isArray(rowData) && i < rowData.length) {
                        cellValue = rowData[i] || '';
                    }
                }
                var dataCellWidth = (type === 'main-merged' || type === 'merged' || type === 'merged2') ? 'width: auto; min-width: 120px; max-width: none; white-space: nowrap; padding: 8px 12px; ' : '';
                // Apply color formatting and handle pipe separators
                var displayValue = cellValue;
                if (type === 'main-merged' || type === 'merged' || type === 'merged2') {
                    // For main merged table, remove pipe and format with colors side by side
                    if (cellValue && cellValue.includes(' | ')) {
                        var parts = cellValue.split(' | ');
                        var t1Value = parts[0] && parts[0] !== '-' ? parts[0] : '';
                        var t2Value = parts[1] && parts[1] !== '-' ? parts[1] : '';
                        var t1Formatted = t1Value ? '<span style="color: #8B4513; font-weight: bold;">' + t1Value + '</span>' : '-';
                        var t2Formatted = t2Value ? '<span style="color: #800080; font-weight: bold;">' + t2Value + '</span>' : '-';
                        // Display with internal dashed separator between t1 and t2
                        displayValue = '<div class="merged-cell-separator" style="display:flex;justify-content:space-around;align-items:center;">' +
                            '<div class="cell-data" style="flex:1;text-align:center;border-right:2px dashed #666;padding-right:8px;margin-right:8px;">' + t1Formatted + '</div>' +
                            '<div class="cell-data" style="flex:1;text-align:center;">' + t2Formatted + '</div>' +
                            '</div>';
                    }
                } else if (type === 'source-from-merged' || type === 'target-from-merged' || type === 'source' || type === 'target') {
                    if (cellValue && cellValue.includes(' | ')) {
                        var parts = cellValue.split(' | ');
                        var t1Value = parts[0] && parts[0] !== '-' ? parts[0] : '';
                        var t2Value = parts[1] && parts[1] !== '-' ? parts[1] : '';
                        if (type === 'source-from-merged' || type === 'source') {
                            displayValue = '<span style="color: #8B4513; font-weight: bold;">' + cellValue + '</span>';
                        } else if (type === 'target-from-merged' || type === 'target') {
                            displayValue = '<span style="color: #800080; font-weight: bold;">' + cellValue + '</span>';
                        }
                    } else if (cellValue && cellValue !== '' && cellValue !== '-') {
                        // If no pipe separator but has value, apply appropriate color based on table type
                        if (type === 'source-from-merged' || type === 'source') {
                            displayValue = '<span style="color: #8B4513; font-weight: bold;">' + cellValue + '</span>';
                        } else if (type === 'target-from-merged' || type === 'target') {
                            displayValue = '<span style="color: #800080; font-weight: bold;">' + cellValue + '</span>';
                        }
                    }
                }
                html += '<td style="border: 1px solid #333; padding: ' + cellPadding + '; background: white; text-align: center; font-weight: bold; ' + dataCellWidth + '">' + displayValue + '</td>';
            }
            html += '</tr>';
            dataRowIndex++; // Move to next data row
        }
    }
    return html;
}
function displaySimpleMapping(resultData) {
    var sourceContainer = document.getElementById('sourceTableDisplay');
    var targetContainer = document.getElementById('targetTableDisplay');
    var summaryContainer = document.getElementById('mappingSummary');
    function extractHMDCols(d) {
        if (!d) return [];
        var key = Object.keys(d).find(function (k) { return k.endsWith('.HMD'); });
        var cols = key ? (d[key] || []) : [];
        return cols.map(function (c) { return String(c); });
    }
    var srcCols = extractHMDCols(sourceData);
    var tgtCols = extractHMDCols(targetData);
    var matches = [];
    if (resultData && Array.isArray(resultData.column_matches)) {
        matches = resultData.column_matches;
    } else if (resultData && Array.isArray(resultData.matches)) {
        matches = resultData.matches;
    }
    if (!matches.length) {
        var tset = new Set(tgtCols.map(function (x) { return x.toLowerCase(); }));
        matches = srcCols
            .filter(function (s) { return tset.has(String(s).toLowerCase()); })
            .map(function (n) { return { source: n, target: n, confidence: 1.0 }; });
    }
    function renderList(cols, side) {
        var wrap = document.createElement('div');
        wrap.className = 'simple-list';
        cols.forEach(function (name, i) {
            var item = document.createElement('div');
            item.className = 'simple-item';
            // Handle both old and new column name formats
            var displayName = name;
            if (name.includes('.HMD.')) {
                displayName = name.replace(/^.*\.HMD\./, '');
            } else if (name.includes('.')) {
                displayName = name.split('.').pop();
            }
            item.textContent = displayName;
            item.setAttribute('data-side', side);
            item.setAttribute('data-col', name);
            item.setAttribute('data-idx', String(i));
            item.id = side + '-col-' + i;
            wrap.appendChild(item);
        });
        return wrap;
    }
    var leftBox = document.createElement('div');
    var rightBox = document.createElement('div');
    leftBox.style.flex = '1';
    rightBox.style.flex = '1';
    var leftTitle = document.createElement('h4');
    leftTitle.textContent = 'Source Columns';
    var rightTitle = document.createElement('h4');
    rightTitle.textContent = 'Target Columns';
    leftTitle.style.margin = rightTitle.style.margin = '0 0 8px 0';
    leftBox.appendChild(leftTitle);
    leftBox.appendChild(renderList(srcCols, 'source'));
    rightBox.appendChild(rightTitle);
    rightBox.appendChild(renderList(tgtCols, 'target'));
    sourceContainer.innerHTML = '';
    targetContainer.innerHTML = '';
    sourceContainer.appendChild(leftBox);
    targetContainer.appendChild(rightBox);
    var count = Array.isArray(matches) ? matches.length : 0;
    var pre = document.createElement('pre');
    pre.style.textAlign = 'left';
    pre.style.whiteSpace = 'pre-wrap';
    pre.style.fontFamily = 'ui-monospace, SFMono-Regular, Menlo, Consolas, monospace';
    pre.style.background = '#fafafa';
    pre.style.border = '1px solid #e5e7eb';
    pre.style.padding = '12px';
    pre.style.borderRadius = '8px';
    pre.style.fontSize = '13px';
    pre.textContent = 'Mappings: ' + count;
    summaryContainer.innerHTML = '';
    summaryContainer.appendChild(pre);
    setTimeout(function () { drawSimpleLinesByIndex(matches); }, 0);
    document.getElementById('tableMappingView').style.display = 'block';
}
// Function to create table data from Merged_Data JSON with t1 | t2 format
function createMergedTableData(mergedData, processedHmd, processedVmd) {
    console.log('[START] createMergedTableData called with parameters:', { mergedData, processedHmd, processedVmd });
    // Handle both object format (new) and array format (old)
    if (!mergedData || !processedHmd || !processedVmd) {
        console.log('âŒ No merged data available or invalid parameters:', { mergedData: !!mergedData, processedHmd: !!processedHmd, processedVmd: !!processedVmd });
        return {};
    }
    // Convert object format to consistent processing format
    var dataToProcess = mergedData;
    if (typeof mergedData === 'object' && !Array.isArray(mergedData)) {
        // New format: {"Bleeding.(n=35)": {"Age, meanÂ±SD,years": {"t1": "74.0Â±8.1", "t2": "75.9Â±7.9"}}}
        console.log('[OK] Processing object format Merged_Data');
        dataToProcess = [mergedData]; // Wrap in array for consistent processing
    } else if (Array.isArray(mergedData)) {
        // Old format: [{"HMD.Bleeding.(n=35)": {"VMD.Age, meanÂ±SD,y": {"t1": "74.0Â±8.1", "t2": ""}}}]
        console.log('[OK] Processing array format Merged_Data');
        dataToProcess = mergedData;
    } else {
        console.log('âŒ Unknown Merged_Data format:', typeof mergedData);
        return {};
    }
    console.log('[OK] Creating merged table data from:', { mergedData, processedHmd, processedVmd });
    var tableData = {};
    // Create mapping lookup for faster access
    var dataLookup = {};
    if (typeof mergedData === 'object' && !Array.isArray(mergedData)) {
        // NEW FORMAT: Direct object {"Bleeding.(n=35)": {"Age, meanÂ±SD,years": {"t1": "74.0Â±8.1", "t2": "75.9Â±7.9"}}}
        // OR MIXED FORMAT: {"HMD.Bleeding.(n=35)": {"VMD.Age, meanÂ±SD": {"t1": "74.0Â±8.1", "t2": ""}}}
        console.log('📂 Processing object format Merged_Data');
        for (var hmdKey in mergedData) {
            var hmdData = mergedData[hmdKey];
            console.log('📂 Processing HMD key:', hmdKey, 'with data:', hmdData);
            // Clean HMD key - remove "HMD." prefix if present
            var cleanHmdKey = hmdKey.startsWith('HMD.') ? hmdKey.replace('HMD.', '') : hmdKey;

            // FLEXIBLE FORMAT SUPPORT: Check if this is VMD_data array format
            if (hmdData.VMD_data && Array.isArray(hmdData.VMD_data)) {
                console.log('✅ Found VMD_data array format for HMD:', cleanHmdKey);
                console.log('✅ VMD_data array length:', hmdData.VMD_data.length);
                // Process VMD_data array: [{"Back to High-Impact Exercise": {"source1": "", "source2": "Immediately"}}]
                for (var vmdIdx = 0; vmdIdx < hmdData.VMD_data.length; vmdIdx++) {
                    var vmdEntry = hmdData.VMD_data[vmdIdx];
                    for (var vmdKey in vmdEntry) {
                        var cellData = vmdEntry[vmdKey];
                        var cleanVmdKey = vmdKey.startsWith('VMD.') ? vmdKey.replace('VMD.', '') : vmdKey;
                        console.log('🔍 VMD key processing:', {
                            original: vmdKey.substring(0, 60),
                            cleaned: cleanVmdKey.substring(0, 60),
                            hasColon: cleanVmdKey.indexOf(':.') !== -1
                        });
                        if (typeof cellData === 'object' && (cellData.t1 !== undefined || cellData.source1 !== undefined)) {
                            var t1Value = cellData.t1 || cellData.source1 || '';
                            var t2Value = cellData.t2 || cellData.source2 || '';
                            var aggregatedValue = cellData.aggregated || null;
                            var cellDataObj = {
                                t1: t1Value,
                                t2: t2Value,
                                aggregated: aggregatedValue
                            };

                            // Store with full key
                            var lookupKey = cleanHmdKey + '|||' + cleanVmdKey;
                            dataLookup[lookupKey] = cellDataObj;
                            console.log('✅ STORED full key:', lookupKey.substring(0, 80));

                            // ALSO store with SHORT VMD key (after the colon) for robust matching
                            // This handles mismatch between Merged_Data keys (e.g., "Operating Data:.Revenue passengers")
                            // and VMD_Merged_Schema keys (e.g., "Revenue passengers")
                            if (cleanVmdKey.indexOf(':.') !== -1) {
                                var shortVmdKey = cleanVmdKey.split(':.').pop();
                                var shortLookupKey = cleanHmdKey + '|||' + shortVmdKey;
                                dataLookup[shortLookupKey] = cellDataObj;
                                console.log('✅ STORED short key:', shortLookupKey.substring(0, 80));
                            }
                        }
                    }
                }
            } else if (typeof hmdData === 'object') {
                // Check for source/target ARRAY format from partition merge
                if (Array.isArray(hmdData.source) || Array.isArray(hmdData.target)) {
                    console.log('✅ Found source/target ARRAY format for VMD key:', hmdKey);
                    // In this format, hmdKey is actually a VMD key like "Financial Data:.Income before taxes"
                    // and hmdData.source/target are arrays of values indexed by HMD column
                    var vmdKey = hmdKey; // This is actually the VMD key
                    var cleanVmdKey = vmdKey.startsWith('VMD.') ? vmdKey.replace('VMD.', '') : vmdKey;
                    var sourceArray = hmdData.source || [];
                    var targetArray = hmdData.target || [];

                    // Create entries for each HMD column
                    for (var hmdIdx = 0; hmdIdx < processedHmd.length; hmdIdx++) {
                        var hmdColKey = '';
                        var hmdItem = processedHmd[hmdIdx];
                        if (typeof hmdItem === 'string') {
                            hmdColKey = hmdItem;
                        } else if (hmdItem && typeof hmdItem === 'object') {
                            for (var k in hmdItem) {
                                if (k.startsWith('attribute') && typeof hmdItem[k] === 'string') {
                                    hmdColKey = hmdItem[k];
                                    break;
                                }
                            }
                        }

                        if (hmdColKey) {
                            // Get values at this HMD column index position
                            // The array index maps to each HMD child column
                            var t1Value = '';
                            var t2Value = '';

                            // Use hmdIdx to get value at correct position
                            if (hmdIdx < sourceArray.length && sourceArray[hmdIdx]) {
                                t1Value = sourceArray[hmdIdx].toString().trim();
                            }
                            if (hmdIdx < targetArray.length && targetArray[hmdIdx]) {
                                t2Value = targetArray[hmdIdx].toString().trim();
                            }

                            var lookupKey = hmdColKey + '|||' + cleanVmdKey;
                            console.log('✅ ARRAY FORMAT STORING:', lookupKey.substring(0, 80), '→ t1:', t1Value, 't2:', t2Value, 'at idx:', hmdIdx);
                            dataLookup[lookupKey] = {
                                t1: t1Value,
                                t2: t2Value,
                                aggregated: null
                            };
                        }
                    }
                } else {
                    // Original t1/t2 object format
                    for (var vmdKey in hmdData) {
                        var cellData = hmdData[vmdKey];
                        console.log('📂 Processing VMD key:', vmdKey, 'with cell data:', cellData);
                        // Clean VMD key - remove "VMD." prefix if present
                        var cleanVmdKey = vmdKey.startsWith('VMD.') ? vmdKey.replace('VMD.', '') : vmdKey;
                        if (typeof cellData === 'object' && (cellData.t1 !== undefined || cellData.source1 !== undefined)) {
                            var lookupKey = cleanHmdKey + '|||' + cleanVmdKey;
                            var t1Value = cellData.t1 || cellData.source1 || '';
                            var t2Value = cellData.t2 || cellData.source2 || '';
                            var aggregatedValue = cellData.aggregated || null;
                            console.log('📂 UNIFIED FORMAT Key created:', { hmdKey, cleanHmdKey, vmdKey, cleanVmdKey, lookupKey, cellData, t1Value, t2Value, aggregatedValue });
                            dataLookup[lookupKey] = {
                                t1: t1Value,
                                t2: t2Value,
                                aggregated: aggregatedValue
                            };
                        }
                    }
                }
            }
        }
    } else {
        // OLD FORMAT: Array [{"HMD.Bleeding.(n=35)": {"VMD.Age, meanÂ±SD,y": {"t1": "74.0Â±8.1", "t2": ""}}}]
        console.log('📂 Processing OLD array format Merged_Data');
        for (var i = 0; i < dataToProcess.length; i++) {
            var item = dataToProcess[i];
            console.log('📂 Processing merged data item:', item);
            for (var hmdKey in item) {
                var hmdData = item[hmdKey];
                // Clean HMD key - remove "HMD." prefix if present
                var cleanHmdKey = hmdKey.startsWith('HMD.') ? hmdKey.replace('HMD.', '') : hmdKey;

                // ARRAY FORMAT: Also check for VMD_data array format within array items
                if (hmdData.VMD_data && Array.isArray(hmdData.VMD_data)) {
                    console.log('✅ Found VMD_data array in OLD array format for HMD:', cleanHmdKey);
                    console.log('✅ VMD_data array length:', hmdData.VMD_data.length);
                    for (var vmdIdx = 0; vmdIdx < hmdData.VMD_data.length; vmdIdx++) {
                        var vmdEntry = hmdData.VMD_data[vmdIdx];
                        console.log('✅ Processing VMD_data entry #' + vmdIdx + ':', vmdEntry);
                        for (var vmdKey in vmdEntry) {
                            var cellData = vmdEntry[vmdKey];
                            console.log('✅ Processing VMD key:', vmdKey, 'cell data:', cellData);
                            var cleanVmdKey = vmdKey.startsWith('VMD.') ? vmdKey.replace('VMD.', '') : vmdKey;
                            if (typeof cellData === 'object' && (cellData.t1 !== undefined || cellData.source1 !== undefined)) {
                                var lookupKey = cleanHmdKey + '|||' + cleanVmdKey;
                                var t1Value = cellData.t1 || cellData.source1 || '';
                                var t2Value = cellData.t2 || cellData.source2 || '';
                                var aggregatedValue = cellData.aggregated || null;
                                console.log('✅ ARRAY VMD_data STORING:', lookupKey, '→ t1:', t1Value, 't2:', t2Value, 'aggregated:', aggregatedValue);
                                dataLookup[lookupKey] = {
                                    t1: t1Value,
                                    t2: t2Value,
                                    aggregated: aggregatedValue
                                };
                            }
                        }
                    }
                } else {
                    // Standard flat format in array
                    for (var vmdKey in hmdData) {
                        var cellData = hmdData[vmdKey];
                        // Clean VMD key - remove "VMD." prefix if present
                        var cleanVmdKey = vmdKey.startsWith('VMD.') ? vmdKey.replace('VMD.', '') : vmdKey;
                        var lookupKey = cleanHmdKey + '|||' + cleanVmdKey;
                        var t1Value = cellData.t1 || cellData.source1 || '';
                        var t2Value = cellData.t2 || cellData.source2 || '';
                        var aggregatedValue = cellData.aggregated || null;
                        console.log('📂 OLD FORMAT Key created:', { hmdKey, cleanHmdKey, vmdKey, cleanVmdKey, lookupKey, cellData, t1Value, t2Value, aggregatedValue });
                        dataLookup[lookupKey] = {
                            t1: t1Value,
                            t2: t2Value,
                            aggregated: aggregatedValue
                        };
                    }
                }
            }
        }
    }
    console.log('📋 Data lookup created:', dataLookup);
    console.log('📋 Data lookup keys:', Object.keys(dataLookup));
    console.log('📋 Total data entries:', Object.keys(dataLookup).length);
    // Create a reverse mapping to find the exact HMD keys used in the data
    var hmdKeyMapping = {};
    for (var lookupKey in dataLookup) {
        var parts = lookupKey.split('|||');
        if (parts.length === 2) {
            var hmdKey = parts[0];
            var vmdKey = parts[1];
            if (!hmdKeyMapping[hmdKey]) {
                hmdKeyMapping[hmdKey] = hmdKey;
            }
        }
    }
    console.log('ðŸ—ï¸ HMD key mapping from data:', hmdKeyMapping);
    // Process each VMD row - handle both flat and hierarchical structures
    for (var vmdIdx = 0; vmdIdx < processedVmd.length; vmdIdx++) {
        var vmdItem = processedVmd[vmdIdx];
        var vmdTextsToProcess = []; // Array of {vmdText, fullKey} to process

        // Extract VMD text(s) based on structure
        if (typeof vmdItem === 'string') {
            vmdTextsToProcess.push({ vmdText: vmdItem, fullKey: vmdItem });
        } else if (vmdItem && typeof vmdItem === 'object') {
            // Check for hierarchical VMD category
            if (vmdItem.is_vmd_category && vmdItem.fullKeys && vmdItem.children) {
                // Process each child with its full key for data lookup
                for (var ci = 0; ci < vmdItem.children.length; ci++) {
                    var childText = vmdItem.children[ci];
                    var fullKey = vmdItem.fullKeys[ci];
                    vmdTextsToProcess.push({ vmdText: childText, fullKey: fullKey });
                }
                console.log('📂 Processing VMD category:', vmdItem.text, 'with', vmdItem.children.length, 'children');
            } else if (vmdItem['row_level1.attribute1']) {
                vmdTextsToProcess.push({ vmdText: vmdItem['row_level1.attribute1'], fullKey: vmdItem['row_level1.attribute1'] });
            } else {
                // Extract from any attributeX key
                for (var key in vmdItem) {
                    if (key.startsWith('attribute') && typeof vmdItem[key] === 'string') {
                        vmdTextsToProcess.push({ vmdText: vmdItem[key], fullKey: vmdItem[key] });
                        break;
                    }
                }
            }
        }

        // Process all VMD texts
        for (var vti = 0; vti < vmdTextsToProcess.length; vti++) {
            var vmdTextInfo = vmdTextsToProcess[vti];
            var vmdText = vmdTextInfo.vmdText;
            var fullVmdKey = vmdTextInfo.fullKey;

            if (!vmdText) continue;
            console.log('Processing VMD row:', vmdText, '(fullKey:', fullVmdKey, ')');

            // Initialize row in table data using vmdText (child name) to match renderer expectation
            if (!tableData[vmdText]) {
                tableData[vmdText] = {};
            }
            // Process each HMD column using the correct order from processedHmd
            for (var hmdIdx = 0; hmdIdx < processedHmd.length; hmdIdx++) {
                var hmdItem = processedHmd[hmdIdx];
                var hmdKey = null;
                // Extract HMD key - handle both flat and hierarchical structures
                if (typeof hmdItem === 'string') {
                    hmdKey = hmdItem;
                } else if (hmdItem && typeof hmdItem === 'object') {
                    // Extract attribute value from any attributeX key
                    for (var key in hmdItem) {
                        if (key.startsWith('attribute') && typeof hmdItem[key] === 'string') {
                            hmdKey = hmdItem[key];
                            break;
                        }
                    }
                    // Check if this has children
                    if (hmdItem.children && hmdItem.children.length > 0) {
                        // Process children for hierarchical HMD
                        for (var childIdx = 0; childIdx < hmdItem.children.length; childIdx++) {
                            var child = hmdItem.children[childIdx];
                            var childKey = (function (c) { if (!c) return ''; if (typeof c === 'string') return c; for (var k in c) { if ((k.indexOf('attribute') !== -1 || k.indexOf('child_level') !== -1) && typeof c[k] === 'string') return c[k]; } return ''; })(child);
                            if (childKey) {
                                var fullHmdKey = hmdKey + '.' + childKey;
                                var lookupKey = fullHmdKey + '|||' + fullVmdKey;
                                var cellData = dataLookup[lookupKey];
                                // If not found, try alternate key matching approaches
                                if (!cellData) {
                                    // Try different key combinations for robustness
                                    var altKeys = [
                                        fullHmdKey + '|||' + fullVmdKey,
                                        fullHmdKey.replace(/\s+/g, ' ').trim() + '|||' + fullVmdKey.replace(/\s+/g, ' ').trim(),
                                        fullHmdKey + '|||' + vmdText.replace(/,\s*/g, ', ')  // fallback
                                    ];
                                    for (var altIdx = 0; altIdx < altKeys.length; altIdx++) {
                                        if (dataLookup[altKeys[altIdx]]) {
                                            cellData = dataLookup[altKeys[altIdx]];
                                            lookupKey = altKeys[altIdx];
                                            break;
                                        }
                                    }
                                }
                                console.log('📂  Schema-ordered data lookup (child):', { lookupKey, cellData, vmdText, fullVmdKey, hmdKey: fullHmdKey, hmdIdx, childIdx, tableData_vmdText: tableData[vmdText] });

                                if (cellData) {
                                    var cellContent;
                                    // Check if aggregated value exists (from merge value strategy)
                                    if (cellData.aggregated) {
                                        // Display single aggregated value
                                        cellContent = cellData.aggregated;
                                    } else {
                                        // Display t1/t2 split
                                        var t1Value = (cellData.t1 || cellData.source1) ? (cellData.t1 || cellData.source1).toString() : '-';
                                        var t2Value = (cellData.t2 || cellData.source2) ? (cellData.t2 || cellData.source2).toString() : '-';
                                        cellContent = t1Value + ' | ' + t2Value;
                                    }
                                    tableData[vmdText][fullHmdKey] = cellContent;
                                    console.log('[OK] Populated schema-ordered cell (child):', { vmd: vmdText, hmd: fullHmdKey, content: cellContent, position: hmdIdx + '.' + childIdx });
                                } else {
                                    // Set empty content for missing data with simple format
                                    tableData[vmdText][fullHmdKey] = '- | -';
                                    console.log('❌ No data found for lookup key (child):', lookupKey);
                                }
                            }
                        }
                        continue; // Skip flat processing for hierarchical items
                    }
                }
                if (hmdKey !== null && hmdKey !== undefined) {
                    var lookupKey = hmdKey + '|||' + fullVmdKey;
                    var cellData = dataLookup[lookupKey];
                    // If not found, try alternate key matching approaches
                    if (!cellData) {
                        // Try different key combinations for robustness
                        var altKeys = [
                            hmdKey + '|||' + fullVmdKey,
                            hmdKey.replace(/\s+/g, ' ').trim() + '|||' + fullVmdKey.replace(/\s+/g, ' ').trim(),
                            hmdKey + '|||' + vmdText.replace(/,\s*/g, ', ')  // normalize comma spacing
                        ];

                        // Also try SHORT VMD key (after the colon) for robust matching
                        // This handles VMD_Merged_Schema with full keys like "Operating Data:.Revenue passengers"
                        if (fullVmdKey.indexOf(':.') !== -1) {
                            var shortVmd = fullVmdKey.split(':.').pop();
                            altKeys.push(hmdKey + '|||' + shortVmd);
                        } else if (fullVmdKey.indexOf('.') !== -1) {
                            // Also try simple dot split if the key is just parent.child
                            var shortVmd = fullVmdKey.split('.').pop();
                            altKeys.push(hmdKey + '|||' + shortVmd);
                        }

                        for (var altIdx = 0; altIdx < altKeys.length; altIdx++) {
                            if (dataLookup[altKeys[altIdx]]) {
                                cellData = dataLookup[altKeys[altIdx]];
                                lookupKey = altKeys[altIdx];
                                break;
                            }
                        }
                    }
                    console.log('📂 Schema-ordered data lookup:', { lookupKey, cellData, vmdText, hmdKey, hmdIdx });
                    if (cellData) {
                        var cellContent;
                        // Check if aggregated value exists (from merge value strategy)
                        if (cellData.aggregated) {
                            // Display single aggregated value
                            var aggregatedFormatted = '<span style="color: #2E7D32; font-weight: bold;">' + cellData.aggregated + '</span>';
                            cellContent = '<div style="display: table; width: 100%; min-height: 20px; table-layout: fixed;"><div style="display: table-cell; width: 100%; text-align: center; vertical-align: middle; padding: 2px; box-sizing: border-box; word-wrap: break-word; overflow: hidden;">' + aggregatedFormatted + '</div></div>';
                        } else {
                            // Display t1/t2 split
                            var t1Value = (cellData.t1 || cellData.source1) ? (cellData.t1 || cellData.source1).toString() : '-';
                            var t2Value = (cellData.t2 || cellData.source2) ? (cellData.t2 || cellData.source2).toString() : '-';
                            // Return simple "t1 | t2" format for renderVmdRowsWithHierarchyJS to parse and format
                            cellContent = t1Value + ' | ' + t2Value;
                        }
                        tableData[vmdText][hmdKey] = cellContent;
                        console.log('[OK] Populated schema-ordered cell:', { vmd: vmdText, hmd: hmdKey, content: cellContent, position: hmdIdx });
                    } else {
                        // Set empty content for missing data with simple format
                        tableData[vmdText][hmdKey] = '- | -';
                        console.log('âŒ No data found for lookup key:', lookupKey);
                    }
                }
            }
        }
    }
    console.log('Final table data structure:', tableData);
    return tableData;
}
// Function to create merged schema table from HMD_Merged_Schema and VMD_Merged_Schema
function createMergedSchemaTable(mergeResultData) {
    if (!mergeResultData) return {};
    // Support both old and new JSON structure formats
    var hmdMerged = mergeResultData.HMD_Merged_Schema ||
        (mergeResultData.Merged_Schema && mergeResultData.Merged_Schema.HMD_Merged_Schema) || [];
    var vmdMerged = mergeResultData.VMD_Merged_Schema ||
        (mergeResultData.Merged_Schema && mergeResultData.Merged_Schema.VMD_Merged_Schema) || [];
    console.log('🔍 Creating merged schema table from:', { hmdMerged_length: hmdMerged.length, vmdMerged_length: vmdMerged.length });
    console.log('🔍 HMD sample items:', hmdMerged.slice(0, 3));
    console.log('🔍 HMD item types:', hmdMerged.slice(0, 3).map(function (item) { return typeof item; }));
    console.log('🔍 VMD sample items:', vmdMerged.slice(0, 3));
    console.log('🔍 VMD item types:', vmdMerged.slice(0, 3).map(function (item) { return typeof item; }));
    if (hmdMerged.length === 0 && vmdMerged.length === 0) return {};
    // Process HMD - handle both object format and string format
    var processedHmd = [];
    var hierarchicalGroups = {};
    var parentOrder = [];
    var simpleItems = [];
    // First pass: identify all hierarchical relationships
    for (var i = 0; i < hmdMerged.length; i++) {
        var item = hmdMerged[i];
        console.log('📂 Analyzing item:', item);
        var attributeValue = null;
        // Handle multiple object formats and string format
        if (typeof item === 'object' && item !== null) {
            // Format 1: {"attribute1": "Bleeding.(n=35)", "children": []}
            if (item.attribute1) {
                attributeValue = item.attribute1.trim();
            }
            // Format 2: {"attribute": "Bleeding.(n=35)", "children": []}  
            else if (item.attribute) {
                attributeValue = item.attribute.trim();
            }
            // Format 3: Direct attribute name as key
            else {
                for (var key in item) {
                    if (key.startsWith('attribute') && typeof item[key] === 'string') {
                        attributeValue = item[key].trim();
                        break;
                    }
                    // Handle case where attribute name is the key itself
                    if (typeof item[key] === 'object' || typeof item[key] === 'string') {
                        if (key !== 'children') {
                            attributeValue = key.trim();
                            break;
                        }
                    }
                }
            }
        } else if (typeof item === 'string') {
            attributeValue = item.trim();
        }
        console.log('📂 Extracted attribute value:', attributeValue, 'from item:', item);
        if (attributeValue !== null && attributeValue !== undefined) {
            if (attributeValue.indexOf('.') !== -1) {
                var parts = attributeValue.split('.', 2);
                var parent = parts[0].trim();
                var child = parts[1].trim();
                console.log('ðŸ‘¨â€ðŸ‘©â€ðŸ‘§â€ðŸ‘¦ Found parent-child:', { parent, child });
                if (!hierarchicalGroups[parent]) {
                    hierarchicalGroups[parent] = [];
                    parentOrder.push(parent);
                }
                hierarchicalGroups[parent].push(child);
            } else {
                if (attributeValue === '') {
                    console.log('⏭️ Skipping empty-string HMD attribute');
                    continue;
                }
                console.log('📂¸ Simple item found:', attributeValue);
                simpleItems.push({
                    text: attributeValue,
                    position: i
                });
            }
        }
    }
    console.log('📊 Analysis complete:');
    console.log('   - Hierarchical groups:', hierarchicalGroups);
    console.log('   - Parent order:', parentOrder);
    console.log('   - Simple items:', simpleItems);
    // Process HMD_Merged_Schema items directly in EXACT order - no reordering
    for (var i = 0; i < hmdMerged.length; i++) {
        var item = hmdMerged[i];
        if (typeof item === 'object' && item !== null) {
            var attributeValue = null;
            // Extract attribute value from any attributeX key
            for (var key in item) {
                if (key.startsWith('attribute') && typeof item[key] === 'string') {
                    attributeValue = item[key];
                    break;
                }
            }
            if (attributeValue !== null && attributeValue !== undefined && attributeValue !== '') { // Only process if valid attribute found (skip empty strings)
                // Check if this is a dot-notation item (like "Bleeding.(n=35)")
                if (attributeValue.indexOf('.') !== -1) {
                    console.log('📂 Processing dot-notation format in order:', attributeValue);
                    var parts = attributeValue.split('.', 2);
                    var parent = parts[0].trim();
                    var child = parts[1].trim();
                    // Create hierarchical structure for this item or append to previous if same parent
                    var addedToExisting = false;
                    if (processedHmd.length > 0) {
                        var lastItem = processedHmd[processedHmd.length - 1];
                        if (typeof lastItem === 'object' && lastItem.attribute1 === parent && lastItem.children) {
                            lastItem.children.push({ 'child_level1.attribute1': child });
                            addedToExisting = true;
                            console.log('[OK] Appended object child to existing parent:', { parent: parent, child: child });
                        }
                    }

                    if (!addedToExisting) {
                        processedHmd.push({
                            'attribute1': parent,
                            'children': [{ 'child_level1.attribute1': child }]
                        });
                        console.log('[OK] Added new dot-notation object in order:', { parent: parent, child: child });
                    }
                } else {
                    // Check if this item has children array
                    if (item.children && Array.isArray(item.children) && item.children.length > 0) {
                        console.log('📂 Found children array for:', attributeValue, '- expanding', item.children.length, 'children');
                        // Expand each child as a separate column entry: "Parent.Child"
                        for (var ci = 0; ci < item.children.length; ci++) {
                            var child = item.children[ci];
                            var childValue = (function (c) { if (!c) return ''; if (typeof c === 'string') return c; for (var k in c) { if ((k.indexOf('attribute') !== -1 || k.indexOf('child_level') !== -1) && typeof c[k] === 'string') return c[k]; } return ''; })(child);
                            if (childValue) {
                                var fullKey = attributeValue + '.' + childValue;
                                console.log('📂 Adding child column:', fullKey);
                                processedHmd.push(fullKey);
                            }
                        }
                    } else {
                        // Simple item with no children
                        // CRITICAL: Check if this item is actually a parent of other items
                        if (hierarchicalGroups[attributeValue]) {
                            console.log('⏭️ Skipping parent item that acts as container:', attributeValue);
                        } else {
                            console.log('📂¸ Adding simple item in order:', attributeValue);
                            processedHmd.push(attributeValue);
                        }
                    }
                }
            } // End of attributeValue check
        } else if (typeof item === 'string') {
            var attributeValue = item.trim();
            if (!attributeValue) continue; // skip empty strings
            if (attributeValue !== null && attributeValue !== undefined && attributeValue.indexOf('.') !== -1) {
                console.log('📂  Processing dot-notation string in order:', attributeValue);
                var parts = attributeValue.split('.', 2);
                var parent = parts[0].trim();
                var child = parts[1].trim();

                // Check if the PREVIOUS item in processedHmd is the SAME parent.
                // If so, append to its children instead of creating a new parent object.
                var addedToExisting = false;
                if (processedHmd.length > 0) {
                    var lastItem = processedHmd[processedHmd.length - 1];
                    if (typeof lastItem === 'object' && lastItem.attribute1 === parent && lastItem.children) {
                        lastItem.children.push({ 'child_level1.attribute1': child });
                        addedToExisting = true;
                        console.log('[OK] Appended child to existing parent:', { parent: parent, child: child });
                    }
                }

                if (!addedToExisting) {
                    processedHmd.push({
                        'attribute1': parent,
                        'children': [{ 'child_level1.attribute1': child }]
                    });
                    console.log('[OK] Added new dot-notation item in order:', { parent: parent, child: child });
                }
            } else {
                processedHmd.push(attributeValue);
            }
        }
    }
    // Process VMD - handle multiple object formats and string format
    var processedVmd = [];
    // First, collect all VMD items and group by parent
    var vmdGroups = {};
    var vmdGroupOrder = [];
    var flatVmdItems = [];

    for (var i = 0; i < vmdMerged.length; i++) {
        var item = vmdMerged[i];
        var attributeValue = null;
        if (typeof item === 'object' && item !== null) {
            if (item.attribute1) {
                attributeValue = item.attribute1.trim();
            } else if (item.attribute) {
                attributeValue = item.attribute.trim();
            } else {
                for (var key in item) {
                    if (key.startsWith('attribute') && typeof item[key] === 'string') {
                        attributeValue = item[key].trim();
                        break;
                    }
                }
            }
        } else if (typeof item === 'string') {
            attributeValue = item.trim();
        }

        if (attributeValue !== null && attributeValue !== undefined) {
            flatVmdItems.push(attributeValue);
            // Check if this has a period separator for hierarchy
            if (attributeValue.indexOf('.') !== -1) {
                var dotIndex = attributeValue.indexOf('.');
                var parent = attributeValue.substring(0, dotIndex).trim();
                var child = attributeValue.substring(dotIndex + 1).trim();

                if (!vmdGroups[parent]) {
                    vmdGroups[parent] = [];
                    vmdGroupOrder.push(parent);
                }
                vmdGroups[parent].push({
                    fullKey: attributeValue,
                    child: child
                });
            } else {
                // No separator - treat as standalone item
                if (!vmdGroups[attributeValue]) {
                    vmdGroups[attributeValue] = [];
                    vmdGroupOrder.push(attributeValue);
                }
            }
        }
    }

    console.log('📂 VMD Groups created:', vmdGroupOrder.length, 'groups');
    console.log('📂 VMD Group order:', vmdGroupOrder);

    // Build processedVmd with hierarchical structure
    for (var gi = 0; gi < vmdGroupOrder.length; gi++) {
        var groupKey = vmdGroupOrder[gi];
        var children = vmdGroups[groupKey];

        if (children && children.length > 0) {
            // This is a category with children
            processedVmd.push({
                is_vmd_category: true,
                text: groupKey,
                children: children.map(function (c) { return c.child; }),
                fullKeys: children.map(function (c) { return c.fullKey; })
            });
            console.log('📂 Added VMD category:', groupKey, 'with', children.length, 'children');
        } else {
            // Standalone item with no children
            processedVmd.push(groupKey);
        }
    }

    // Store the flat VMD items for data lookup
    var flatVmdForLookup = flatVmdItems;

    console.log('✅ Processed HMD count:', processedHmd.length);
    console.log('✅ Processed HMD samples:', processedHmd.slice(0, 3));
    console.log('✅ Processed HMD sample types:', processedHmd.slice(0, 3).map(function (item) { return typeof item; }));
    console.log('✅ Processed VMD count:', processedVmd.length);
    console.log('✅ Processed VMD samples:', processedVmd.slice(0, 3));
    // Create the merged table structure
    var mergedTable = {
        'MergedTable.HMD': processedHmd,
        'MergedTable.VMD': processedVmd,
        'MergedTable.VMD_HEADER': 'Merged Attributes'
    };
    // Create table data from Merged_Data for actual cell population - support both formats
    var mergedDataSource = mergeResultData.Merged_Data || [];
    console.log('✅ Merged_Data type:', Array.isArray(mergedDataSource) ? 'array' : typeof mergedDataSource);
    console.log('✅ Merged_Data length:', mergedDataSource.length || Object.keys(mergedDataSource).length);
    var tableData = createMergedTableData(mergedDataSource, processedHmd, processedVmd);
    console.log('✅ Table data populated cells:', Object.keys(tableData).length);
    mergedTable['MergedTable.Data'] = tableData;
    console.log('Final merged table:', mergedTable);
    console.log('Generated table data:', tableData);
    return mergedTable;
}
// Function to apply dashed border styling to merged schema table
function addVerticalDashedLines(containerId) {
    var container = document.getElementById(containerId);
    if (!container) return;
    var table = container.querySelector('table');
    if (!table) return;
    // Remove any existing overlays
    var existingOverlays = container.querySelectorAll('.column-separators-overlay');
    existingOverlays.forEach(function (overlay) { overlay.remove(); });
    var tableRect = table.getBoundingClientRect();
    var thead = table.querySelector('thead');
    if (!thead) return;
    var hmdMainRow = thead.querySelector('tr:first-child');
    var t1t2Row = thead.querySelector('tr.t1-t2-subheader');
    if (!t1t2Row) {
        console.log('No t1/t2 row - skipping dashed lines');
        return;
    }
    var hmdMainRect = hmdMainRow.getBoundingClientRect();
    var t1t2Rect = t1t2Row.getBoundingClientRect();
    var headerHeightToT1T2 = t1t2Rect.top - hmdMainRect.top;
    var t1t2Cells = t1t2Row.querySelectorAll('td, th');
    var overlay = document.createElement('div');
    overlay.className = 'column-separators-overlay';
    overlay.style.position = 'absolute';
    overlay.style.top = '0px';
    overlay.style.left = '0px';
    overlay.style.width = table.offsetWidth + 'px';
    overlay.style.height = table.offsetHeight + 'px';
    overlay.style.pointerEvents = 'none';
    overlay.style.zIndex = '10';
    // Draw a dashed line at the left edge of every t2 cell (between t1 and t2 in each pair)
    var prevWasT1 = false;
    for (var i = 1; i < t1t2Cells.length; i++) {
        var cellText = (t1t2Cells[i].textContent || '').trim().toLowerCase();
        if (cellText === 't1') { prevWasT1 = true; continue; }
        if (cellText === 't2' && prevWasT1) {
            prevWasT1 = false;
            var cellRect = t1t2Cells[i].getBoundingClientRect();
            var separatorX = cellRect.left - tableRect.left;
            if (separatorX < 10) continue;
            var line = document.createElement('div');
            line.style.position = 'absolute';
            line.style.width = '2px';
            line.style.height = 'calc(100% - ' + headerHeightToT1T2 + 'px)';
            line.style.background = 'repeating-linear-gradient(to bottom, #666, #666 4px, transparent 4px, transparent 8px)';
            line.style.zIndex = '5';
            line.style.left = separatorX + 'px';
            line.style.top = headerHeightToT1T2 + 'px';
            overlay.appendChild(line);
        } else { prevWasT1 = false; }
    }
    var scrollWrapper = table.parentElement;
    (scrollWrapper || container).appendChild(overlay);
}

// Function to display merged schema mappings
function displayMergedSchemaMappings(mergeResultData) {
    console.log('🔄 displayMergedSchemaMappings called with:', mergeResultData);
    console.log('📂 Current sourceData:', sourceData);
    console.log('📂 Current targetData:', targetData);
    // Create merged schema table
    var mergedSchemaTable = createMergedSchemaTable(mergeResultData);
    if (Object.keys(mergedSchemaTable).length === 0) {
        return; // No merged schema to display
    }
    // Simply prepare content for both tabs - lines will draw when user visits each tab
    displayMergedToSourceMapping(mergedSchemaTable, mergeResultData);
    displayMergedToTargetMapping(mergedSchemaTable, mergeResultData);
}
// Function to display Merged → Source mapping
function displayMergedToSourceMapping(mergedSchemaTable, mergeResultData) {
    // Find the mapping-tables-container directly in merged-source-tab
    var mappingTablesContainer = document.querySelector('#merged-source-tab .mapping-tables-container');
    if (!mappingTablesContainer) {
        console.error('mapping-tables-container not found in merged-source-tab');
        return;
    }
    // Create mapping data - support both old and new JSON structure formats
    var hmdMappings = mergeResultData.HMD_Map_Schema1 ||
        (mergeResultData.Map_Schema1 && mergeResultData.Map_Schema1.HMD_Map_Schema1) || [];
    var vmdMappings = mergeResultData.VMD_Map_Schema1 ||
        (mergeResultData.Map_Schema1 && mergeResultData.Map_Schema1.VMD_Map_Schema1) || [];
    var hmdMergedSchema = mergeResultData.HMD_Merged_Schema ||
        (mergeResultData.Merged_Schema && mergeResultData.Merged_Schema.HMD_Merged_Schema) || [];
    var vmdMergedSchema = mergeResultData.VMD_Merged_Schema ||
        (mergeResultData.Merged_Schema && mergeResultData.Merged_Schema.VMD_Merged_Schema) || [];
    console.log('📂 HMD_Map_Schema1 data:', hmdMappings);
    console.log('📂 VMD_Map_Schema1 data:', vmdMappings);
    console.log('📂 Total HMD mappings:', hmdMappings.length);
    console.log('📂 Total VMD mappings:', vmdMappings.length);
    // Create simple mapping display like simple tables
    var mappingHTML = createComplexToSimpleMappingTable(
        hmdMappings, vmdMappings,
        hmdMergedSchema, vmdMergedSchema,
        'Source', 't1'
    );
    // Place mapping directly in mapping-tables-container (100% width)
    mappingTablesContainer.innerHTML = mappingHTML;
    // Apply coloring to merged source table content
    setTimeout(function () {
        var checkbox = document.getElementById('sourceDataToggle');
        var showData = checkbox ? checkbox.checked : true;
        // Find any tables within this container and apply coloring
        var tables = mappingTablesContainer.querySelectorAll('table');
        tables.forEach(function (table) {
            var cells = table.querySelectorAll('[data-cell-value]');
            cells.forEach(function (cell) {
                if (showData && cell.dataset.cellValue) {
                    cell.style.backgroundColor = '#e8f5e9';
                    cell.textContent = cell.dataset.cellValue;
                } else {
                    cell.style.backgroundColor = '';
                    cell.textContent = cell.dataset.originalText || '';
                }
            });
        });
    }, 100);
    // Check if user is currently on this specific tab (more robust checking)
    var sourceTab = document.querySelector('#merged-source-tab');
    var isCurrentTabActive = sourceTab && sourceTab.classList.contains('active');
    console.log('📂 Source tab element found:', !!sourceTab);
    console.log('📂 Source tab classes:', sourceTab ? sourceTab.className : 'no element');
    console.log('📂 Is source tab active?', isCurrentTabActive);
    if (isCurrentTabActive) {
        console.log('[AUTO] User is on Source tab - drawing lines with proper timing');
        // Use proper timing to ensure DOM elements are fully rendered
        requestAnimationFrame(function () {
            setTimeout(function () {
                console.log('🔄 Source tab - First attempt to draw lines...');
                drawComplexMappingLines(mappingTablesContainer);
            }, 300);
        });
        // Additional attempts with increasing delays
        setTimeout(function () {
            console.log('🔄 Source tab - Second attempt to draw lines...');
            drawComplexMappingLines(mappingTablesContainer);
        }, 800);
        setTimeout(function () {
            console.log('🔄 Source tab - Final attempt to draw lines...');
            drawComplexMappingLines(mappingTablesContainer);
        }, 1500);
    } else {
        console.log('[AUTO] User not on Source tab - but will draw lines when they switch to it');
    }
}
// Function to display Merged → Target mapping
function displayMergedToTargetMapping(mergedSchemaTable, mergeResultData) {
    // Find the mapping-tables-container directly in merged-target-tab
    var mappingTablesContainer = document.querySelector('#merged-target-tab .mapping-tables-container');
    if (!mappingTablesContainer) {
        console.error('mapping-tables-container not found in merged-target-tab');
        return;
    }
    // Create mapping data - support both old and new JSON structure formats
    var hmdMappings = mergeResultData.HMD_Map_Schema2 ||
        (mergeResultData.Map_Schema2 && mergeResultData.Map_Schema2.HMD_Map_Schema2) || [];
    var vmdMappings = mergeResultData.VMD_Map_Schema2 ||
        (mergeResultData.Map_Schema2 && mergeResultData.Map_Schema2.VMD_Map_Schema2) || [];
    var hmdMergedSchema = mergeResultData.HMD_Merged_Schema ||
        (mergeResultData.Merged_Schema && mergeResultData.Merged_Schema.HMD_Merged_Schema) || [];
    var vmdMergedSchema = mergeResultData.VMD_Merged_Schema ||
        (mergeResultData.Merged_Schema && mergeResultData.Merged_Schema.VMD_Merged_Schema) || [];
    // Create simple mapping display like simple tables
    var mappingHTML = createComplexToSimpleMappingTable(
        hmdMappings, vmdMappings,
        hmdMergedSchema, vmdMergedSchema,
        'Target', 't2'
    );
    // Place mapping directly in mapping-tables-container (100% width)
    mappingTablesContainer.innerHTML = mappingHTML;
    // Apply coloring to merged target table content
    setTimeout(function () {
        var checkbox = document.getElementById('targetDataToggle');
        var showData = checkbox ? checkbox.checked : true;
        // Find any tables within this container and apply coloring
        var tables = mappingTablesContainer.querySelectorAll('table');
        tables.forEach(function (table) {
            var cells = table.querySelectorAll('[data-cell-value]');
            cells.forEach(function (cell) {
                if (showData && cell.dataset.cellValue) {
                    cell.style.backgroundColor = '#ffebee';
                    cell.textContent = cell.dataset.cellValue;
                } else {
                    cell.style.backgroundColor = '';
                    cell.textContent = cell.dataset.originalText || '';
                }
            });
        });
    }, 100);
    // Check if user is currently on this specific tab (more robust checking)
    var targetTab = document.querySelector('#merged-target-tab');
    var isCurrentTabActive = targetTab && targetTab.classList.contains('active');
    console.log('📂 Target tab element found:', !!targetTab);
    console.log('📂 Target tab classes:', targetTab ? targetTab.className : 'no element');
    console.log('📂 Is target tab active?', isCurrentTabActive);
    if (isCurrentTabActive) {
        console.log('[AUTO] User is on Target tab - drawing lines with proper timing');
        // Use proper timing to ensure DOM elements are fully rendered
        requestAnimationFrame(function () {
            setTimeout(function () {
                console.log('🔄 Target tab - First attempt to draw lines...');
                drawComplexMappingLines(mappingTablesContainer);
            }, 300);
        });
        // Additional attempts with increasing delays
        setTimeout(function () {
            console.log('🔄 Target tab - Second attempt to draw lines...');
            drawComplexMappingLines(mappingTablesContainer);
        }, 800);
        setTimeout(function () {
            console.log('🔄 Target tab - Final attempt to draw lines...');
            drawComplexMappingLines(mappingTablesContainer);
        }, 1500);
    } else {
        console.log('[AUTO] User not on Target tab - but will draw lines when they switch to it');
    }
}
// Function to create complex to simple mapping table (4 columns with all attributes)
function createComplexToSimpleMappingTable(hmdMappings, vmdMappings, hmdMergedSchema, vmdMergedSchema, direction, schemaField) {
    // Debug each mapping individually
    // console.log('📂 === DEBUG for', direction, 'with schemaField:', schemaField, '===');
    hmdMappings.forEach(function (mapping, idx) {
        console.log('📂 HMD Mapping', idx, ':', mapping, 'schemaField value:', mapping[schemaField]);
    });
    vmdMappings.forEach(function (mapping, idx) {
        console.log('📂 VMD Mapping', idx, ':', mapping, 'schemaField value:', mapping[schemaField]);
    });
    // Create mapping lookup for quick access - support both naming conventions
    var hmdMappingLookup = {};
    hmdMappings.forEach(function (mapping) {
        // Support both: {merged, t1, t2} and {source1, source2}
        var mergedAttr = (mapping.merged || mapping.source1 || '').replace('HMD_Merged_Schema.', '').replace('Merged_Schema.', '');
        var targetAttr = mapping[schemaField] || mapping.source2 || '';
        if (mergedAttr && targetAttr) {
            hmdMappingLookup[mergedAttr] = targetAttr;
            console.log('[MAPPING] HMD:', mergedAttr, '→', targetAttr);
        }
    });
    var vmdMappingLookup = {};
    vmdMappings.forEach(function (mapping) {
        // Support both: {merged, t1, t2} and {source1, source2}
        var mergedAttr = (mapping.merged || mapping.source1 || '').replace('VMD_Merged_Schema.', '').replace('Merged_Schema.', '');
        var targetAttr = mapping[schemaField] || mapping.source2 || '';
        if (mergedAttr && targetAttr) {
            vmdMappingLookup[mergedAttr] = targetAttr;
            console.log('[MAPPING] VMD:', mergedAttr, '→', targetAttr);
        }
    });
    // });
    // SIMPLE APPROACH: Use ONLY the original uploaded schemas for display
    // Mappings are ONLY used for drawing connection lines, NOT for determining what to show
    var sourceHmdAttributes = [];
    var sourceVmdAttributes = [];

    if (direction === 'Source') {
        // For Source: Use original source schema uploaded by user
        sourceHmdAttributes = window.originalSourceHMD || [];
        sourceVmdAttributes = window.originalSourceVMD || [];
        console.log('[SIMPLE] Using Source schemas - HMD:', sourceHmdAttributes.length, 'VMD:', sourceVmdAttributes.length);
    } else {
        // For Target: Use original target schema uploaded by user
        sourceHmdAttributes = window.originalTargetHMD || [];
        sourceVmdAttributes = window.originalTargetVMD || [];
        console.log('[SIMPLE] Using Target schemas - HMD:', sourceHmdAttributes.length, 'VMD:', sourceVmdAttributes.length);
    }

    // FALLBACK: If window variables are empty (e.g., viewing cached results), extract from mappings
    if (sourceHmdAttributes.length === 0) {
        console.log('[FALLBACK] Window variables empty, extracting HMD from mappings');
        var hmdSet = new Set();
        hmdMappings.forEach(function (mapping) {
            var targetAttr = (mapping[schemaField] || mapping.source2 || '').replace('Schema1.', '').replace('Schema2.', '');
            if (targetAttr) {
                hmdSet.add(targetAttr);
            }
        });
        sourceHmdAttributes = Array.from(hmdSet);
        console.log('[FALLBACK] Extracted HMD:', sourceHmdAttributes);
    }

    if (sourceVmdAttributes.length === 0) {
        console.log('[FALLBACK] Window variables empty, extracting VMD from mappings');
        var vmdSet = new Set();
        vmdMappings.forEach(function (mapping) {
            var targetAttr = (mapping[schemaField] || mapping.source2 || '').replace('Schema1.', '').replace('Schema2.', '');
            if (targetAttr) {
                vmdSet.add(targetAttr);
            }
        });
        sourceVmdAttributes = Array.from(vmdSet);
        console.log('[FALLBACK] Extracted VMD:', sourceVmdAttributes);
    }

    console.log('[SIMPLE] Displaying ALL attributes from original upload or mappings');
    console.log('[SIMPLE] Mappings will only be used for drawing connection lines');
    // Direct display using full mapping-tables-container width
    var html = '<div style="width: 100%; height: 100%; padding: 0; margin: 0;">';
    html += '<h3 style="text-align: center; color: #333; margin-bottom: 20px; font-weight: bold; font-size: 18px;">Merged → ' + direction + '</h3>';
    // Container spanning full width with 4 equal columns and gaps for connection lines
    html += '<div class="mapping-container" style="position: relative; display: flex; gap: 4%; width: 100%; height: calc(100% - 60px); align-items: flex-start;">';
    // SVG for connection lines - working positioning
    html += '<svg class="connection-svg" style="position: absolute; top: 0; left: 0; width: 100%; height: 100%; z-index: 999; pointer-events: none; overflow: visible;">';
    html += '</svg>';
    // HMD Section - 44% width (2 columns with larger gap for connection lines)
    html += '<div style="flex: 0 0 44%; position: relative; z-index: 2; display: flex; gap: 6%;">';
    // HMD Merged Column
    html += '<div style="flex: 0 0 47%; min-width: 0;">';
    html += '<h4 style="color: #2E7D32; text-align: center; margin-bottom: 16px; padding: 12px; background: #e8f5e9; border-radius: 8px; font-weight: bold; font-size: 18px;">Merged HMD (' + hmdMergedSchema.length + ')</h4>';
    // Show ALL HMD attributes from merged schema
    hmdMergedSchema.forEach(function (item, index) {
        // Extract attribute value from both formats: string or {"attribute1": "value", "children": []}
        var attr;
        if (typeof item === 'string') {
            attr = item;
        } else if (typeof item === 'object' && item !== null) {
            // Extract from object format - look for any attributeX key
            for (var key in item) {
                if (key.startsWith('attribute') && typeof item[key] === 'string') {
                    attr = item[key];
                    break;
                }
            }
        }
        if (!attr) return; // Skip if no valid attribute found
        var mappedValue = hmdMappingLookup[attr];
        console.log('HMD Merged attr:', attr, 'mappedValue:', mappedValue, 'lookup keys:', Object.keys(hmdMappingLookup));
        var backgroundColor = mappedValue ? '#e8f5e9' : '#f9f9f9';
        var borderColor = mappedValue ? '#4caf50' : '#ddd';
        html += '<div class="merged-hmd-item" data-attribute="' + attr + '" data-index="' + index + '" data-mapped="' + (mappedValue || '') + '" style="background: ' + backgroundColor + '; border: 1px solid ' + borderColor + '; border-radius: 4px; font-weight: bold; padding: 8px 4px; margin: 3px 0; font-size: 18px; color: #333; line-height: 1.3; min-height: 20px; text-align: center;">';
        html += attr;
        html += '</div>';
    });
    html += '</div>';
    // HMD Source/Target Column
    html += '<div style="flex: 0 0 47%; min-width: 0;">';
    html += '<h4 style="color: #2E7D32; text-align: center; margin-bottom: 16px; padding: 12px; background: #e8f5e9; border-radius: 8px; font-weight: bold; font-size: 18px;">' + direction + ' HMD (' + sourceHmdAttributes.length + ')</h4>';
    // Display only actual source attributes (no empty cells)
    var sourceHmdArray = sourceHmdAttributes;
    sourceHmdArray.forEach(function (sourceAttr, index) {
        if (sourceAttr && sourceAttr.trim()) {
            // Find if this source attribute is mapped to any merged attribute
            var mappedToMerged = null;
            for (var mergedAttr in hmdMappingLookup) {
                if (hmdMappingLookup[mergedAttr] && hmdMappingLookup[mergedAttr].includes(sourceAttr)) {
                    mappedToMerged = mergedAttr;
                    break;
                }
            }
            var isCurrentlyMapped = mappedToMerged !== null;
            var backgroundColor = isCurrentlyMapped ? '#e8f5e9' : '#f9f9f9';
            var borderColor = isCurrentlyMapped ? '#4caf50' : '#ddd';
            html += '<div class="source-hmd-item" data-source="' + sourceAttr + '" data-mapped-to="' + (mappedToMerged || '') + '" data-index="' + index + '" style="background: ' + backgroundColor + '; border: 1px solid ' + borderColor + '; border-radius: 4px; padding: 8px 4px; margin: 3px 0; font-weight: bold; font-size: 18px; color: #333; line-height: 1.3; min-height: 20px; text-align: center;">';
            html += sourceAttr;
            html += '</div>';
        }
    });
    html += '</div>';
    html += '</div>';
    // VMD Section - 44% width (2 columns with larger gap for connection lines)
    html += '<div style="flex: 0 0 44%; position: relative; z-index: 2; display: flex; gap: 6%;">';
    // VMD Merged Column
    html += '<div style="flex: 0 0 47%; min-width: 0;">';
    html += '<h4 style="color: #c62828; text-align: center; margin-bottom: 16px; padding: 12px; background: #ffebee; border-radius: 8px; font-weight: bold; font-size: 18px;">Merged VMD (' + vmdMergedSchema.length + ')</h4>';
    // Show ALL VMD attributes from merged schema
    vmdMergedSchema.forEach(function (item, index) {
        // Extract attribute value from both formats: string or {"attribute1": "value", "children": []}
        var attr;
        if (typeof item === 'string') {
            attr = item;
        } else if (typeof item === 'object' && item !== null) {
            // Extract from object format - look for any attributeX key
            for (var key in item) {
                if (key.startsWith('attribute') && typeof item[key] === 'string') {
                    attr = item[key];
                    break;
                }
            }
        }
        if (!attr) return; // Skip if no valid attribute found
        var mappedValue = vmdMappingLookup[attr];
        console.log('VMD Merged attr:', attr, 'mappedValue:', mappedValue, 'lookup keys:', Object.keys(vmdMappingLookup));
        var backgroundColor = mappedValue ? '#ffebee' : '#f9f9f9';
        var borderColor = mappedValue ? '#f44336' : '#ddd';
        html += '<div class="merged-vmd-item" data-attribute="' + attr + '" data-index="' + index + '" data-mapped="' + (mappedValue || '') + '" style="background: ' + backgroundColor + '; border: 1px solid ' + borderColor + '; border-radius: 4px; padding: 8px 4px; margin: 3px 0; font-weight: bold; font-size: 18px; color: #333; line-height: 1.3; min-height: 20px; text-align: center;">';
        html += attr;
        html += '</div>';
    });
    html += '</div>';
    // VMD Source/Target Column
    html += '<div style="flex: 0 0 47%; min-width: 0;">';
    html += '<h4 style="color: #c62828; text-align: center; margin-bottom: 16px; padding: 12px; background: #ffebee; border-radius: 8px; font-weight: bold; font-size: 18px;">' + direction + ' VMD (' + sourceVmdAttributes.length + ')</h4>';
    // Display only actual source attributes (no empty cells)
    var sourceVmdArray = sourceVmdAttributes;
    sourceVmdArray.forEach(function (sourceAttr, index) {
        if (sourceAttr && sourceAttr.trim()) {
            // Find if this source attribute is mapped to any merged attribute
            var mappedToMerged = null;
            for (var mergedAttr in vmdMappingLookup) {
                if (vmdMappingLookup[mergedAttr] && vmdMappingLookup[mergedAttr].includes(sourceAttr)) {
                    mappedToMerged = mergedAttr;
                    break;
                }
            }
            var isCurrentlyMapped = mappedToMerged !== null;
            var backgroundColor = isCurrentlyMapped ? '#ffebee' : '#f9f9f9';
            var borderColor = isCurrentlyMapped ? '#f44336' : '#ddd';
            html += '<div class="source-vmd-item" data-source="' + sourceAttr + '" data-mapped-to="' + (mappedToMerged || '') + '" data-index="' + index + '" style="background: ' + backgroundColor + '; border: 1px solid ' + borderColor + '; border-radius: 4px; padding: 8px 4px; margin: 3px 0; font-size: 18px; font-weight: bold;color: #333; line-height: 1.3; min-height: 20px; text-align: center;">';
            html += sourceAttr;
            html += '</div>';
        }
    });
    html += '</div>'; // Close VMD source column
    html += '</div>'; // Close VMD section
    html += '</div>'; // Close mapping-container
    html += '</div>'; // Close main container
    return html;
}
// Robust function to wait for DOM elements to be properly rendered and visible
function waitForElementsToBeVisible(container, callback, maxAttempts = 10) {
    var attempts = 0;
    function checkVisibility() {
        attempts++;
        console.log('📂 Visibility check attempt', attempts);
        var svg = container.querySelector('.connection-svg');
        if (!svg) {
            console.log('âŒ SVG not found, attempt', attempts);
            if (attempts < maxAttempts) {
                setTimeout(checkVisibility, 200);
            }
            return;
        }
        var containerRect = container.getBoundingClientRect();
        var mappingContainer = container.querySelector('.mapping-container');
        if (!mappingContainer) {
            console.log('âŒ Mapping container not found, attempt', attempts);
            if (attempts < maxAttempts) {
                setTimeout(checkVisibility, 200);
            }
            return;
        }
        var mappingRect = mappingContainer.getBoundingClientRect();
        // Check if elements have non-zero dimensions and are actually in viewport
        if (containerRect.width > 0 && containerRect.height > 0 &&
            mappingRect.width > 0 && mappingRect.height > 0) {
            // Additional check: verify parent tab is actually visible/active
            var parentTab = container.closest('.tab-content');
            if (parentTab) {
                var parentTabRect = parentTab.getBoundingClientRect();
                if (parentTabRect.width === 0 || parentTabRect.height === 0) {
                    console.log('[WARNING] Parent tab not visible - dimensions:', parentTabRect.width, 'x', parentTabRect.height, 'attempt', attempts);
                    if (attempts < maxAttempts) {
                        setTimeout(checkVisibility, 400 + (attempts * 200)); // Longer delay for tab switching
                    }
                    return;
                }
                console.log('[OK] Parent tab is visible:', parentTabRect.width, 'x', parentTabRect.height);
            }
            // Additional check: verify some actual attribute elements exist and are visible
            var mergedHmdItems = container.querySelectorAll('.merged-hmd-item');
            var sourceHmdItems = container.querySelectorAll('.source-hmd-item');
            if (mergedHmdItems.length > 0 && sourceHmdItems.length > 0) {
                // Test the first element to see if it has valid dimensions
                var testRect = mergedHmdItems[0].getBoundingClientRect();
                if (testRect.width > 0 && testRect.height > 0) {
                    console.log('[OK] Elements are visible and ready, calling callback');
                    callback();
                    return;
                }
                console.log('[WARNING] Attribute elements not visible yet - test rect:', testRect.width, 'x', testRect.height, 'attempt', attempts);
            } else {
                console.log('[WARNING] No attribute elements found - HMD:', mergedHmdItems.length, 'Source:', sourceHmdItems.length, 'attempt', attempts);
            }
        }
        console.log('[WARNING] Elements not ready yet - Container:', containerRect.width, 'x', containerRect.height,
            'Mapping:', mappingRect.width, 'x', mappingRect.height, 'attempt', attempts);
        if (attempts < maxAttempts) {
            setTimeout(checkVisibility, 300 + (attempts * 100)); // Increasing delay
        } else {
            console.log('âŒ Max attempts reached, elements may not be visible');
        }
    }
    // Start checking immediately, then use requestAnimationFrame for better timing
    requestAnimationFrame(function () {
        checkVisibility();
    });
}
// SIMPLE TEST FUNCTION - Call this manually from console
function testDrawLines() {
    console.log('[START] MANUAL TEST: Drawing lines for both tabs');
    // Test Source tab
    var sourceContainer = document.querySelector('#merged-source-tab .mapping-tables-container');
    if (sourceContainer) {
        console.log('[START] Testing Source tab lines...');
        drawComplexMappingLinesSimple(sourceContainer);
    }
    // Test Target tab  
    var targetContainer = document.querySelector('#merged-target-tab .mapping-tables-container');
    if (targetContainer) {
        console.log('[START] Testing Target tab lines...');
        drawComplexMappingLinesSimple(targetContainer);
    }
}
// REAL connection lines between mapped attributes
function drawComplexMappingLinesSimple(container) {
    console.log('🎨 REAL: Drawing connection lines for mapped attributes');
    var svg = container.querySelector('.connection-svg');
    if (!svg) {
        console.log('âŒ REAL: No SVG found');
        return;
    }
    console.log('[OK] REAL: SVG found, drawing actual connection lines');
    svg.innerHTML = ''; // Clear existing
    // Get all elements
    var mergedHmdItems = container.querySelectorAll('.merged-hmd-item');
    var sourceHmdItems = container.querySelectorAll('.source-hmd-item');
    var mergedVmdItems = container.querySelectorAll('.merged-vmd-item');
    var sourceVmdItems = container.querySelectorAll('.source-vmd-item');
    console.log('📂 REAL: Found elements - Merged HMD:', mergedHmdItems.length, 'Source HMD:', sourceHmdItems.length);
    var linesDrawn = 0;
    // Draw HMD connection lines (green)
    // console.log('📂 DEBUG: Checking merged HMD items for connections...');
    mergedHmdItems.forEach(function (mergedItem, idx) {
        var mappedValue = mergedItem.getAttribute('data-mapped');
        var mergedAttr = mergedItem.getAttribute('data-attribute');
        console.log('📂 Merged HMD', idx, '- Attr:', mergedAttr, 'Mapped:', mappedValue);
        if (mappedValue && mappedValue.trim()) {
            // Find matching source item
            console.log('📂 Searching for source match for merged attr:', mergedAttr);
            for (var i = 0; i < sourceHmdItems.length; i++) {
                var sourceItem = sourceHmdItems[i];
                var sourceAttr = sourceItem.getAttribute('data-source');
                var mappedToMerged = sourceItem.getAttribute('data-mapped-to');
                console.log('📂 Source HMD', i, '- Source:', sourceAttr, 'MappedTo:', mappedToMerged);
                if (mappedToMerged === mergedAttr && sourceAttr && sourceAttr.trim()) {
                    console.log('🟢 REAL: Drawing HMD line:', mergedAttr, '->', sourceAttr);
                    // Get positions - use mapping-container as consistent reference
                    var mergedRect = mergedItem.getBoundingClientRect();
                    var sourceRect = sourceItem.getBoundingClientRect();
                    // Fix: Use mapping-container (inner container) as reference for consistency  
                    var mappingContainer = container.querySelector('.mapping-container');
                    var containerRect = mappingContainer ? mappingContainer.getBoundingClientRect() : container.getBoundingClientRect();
                    var startX = mergedRect.right - containerRect.left;
                    var startY = mergedRect.top + mergedRect.height / 2 - containerRect.top;
                    var endX = sourceRect.left - containerRect.left;
                    var endY = sourceRect.top + sourceRect.height / 2 - containerRect.top;
                    // Create line
                    var line = document.createElementNS('http://www.w3.org/2000/svg', 'line');
                    line.setAttribute('x1', startX);
                    line.setAttribute('y1', startY);
                    line.setAttribute('x2', endX);
                    line.setAttribute('y2', endY);
                    line.setAttribute('stroke', '#4CAF50');
                    line.setAttribute('stroke-width', '3');
                    line.setAttribute('opacity', '0.8');
                    svg.appendChild(line);
                    linesDrawn++;
                    break;
                } else {
                    console.log('[WARNING] HMD No match:', mappedToMerged, '!==', mergedAttr, 'OR missing sourceAttr:', sourceAttr);
                }
            }
        } else {
            console.log('[WARNING] Merged HMD has no mapped value:', mergedAttr, 'mappedValue:', mappedValue);
        }
    });
    // Draw VMD connection lines (red)
    mergedVmdItems.forEach(function (mergedItem) {
        var mappedValue = mergedItem.getAttribute('data-mapped');
        var mergedAttr = mergedItem.getAttribute('data-attribute');
        if (mappedValue && mappedValue.trim()) {
            // Find matching source item
            for (var i = 0; i < sourceVmdItems.length; i++) {
                var sourceItem = sourceVmdItems[i];
                var sourceAttr = sourceItem.getAttribute('data-source');
                var mappedToMerged = sourceItem.getAttribute('data-mapped-to');
                if (mappedToMerged === mergedAttr && sourceAttr && sourceAttr.trim()) {
                    console.log('📂´ REAL: Drawing VMD line:', mergedAttr, '->', sourceAttr);
                    // Get positions - use mapping-container as consistent reference
                    var mergedRect = mergedItem.getBoundingClientRect();
                    var sourceRect = sourceItem.getBoundingClientRect();
                    // Fix: Use mapping-container (inner container) as reference for consistency  
                    var mappingContainer = container.querySelector('.mapping-container');
                    var containerRect = mappingContainer ? mappingContainer.getBoundingClientRect() : container.getBoundingClientRect();
                    var startX = mergedRect.right - containerRect.left;
                    var startY = mergedRect.top + mergedRect.height / 2 - containerRect.top;
                    var endX = sourceRect.left - containerRect.left;
                    var endY = sourceRect.top + sourceRect.height / 2 - containerRect.top;
                    // Create line
                    var line = document.createElementNS('http://www.w3.org/2000/svg', 'line');
                    line.setAttribute('x1', startX);
                    line.setAttribute('y1', startY);
                    line.setAttribute('x2', endX);
                    line.setAttribute('y2', endY);
                    line.setAttribute('stroke', '#f44336');
                    line.setAttribute('stroke-width', '3');
                    line.setAttribute('opacity', '0.8');
                    svg.appendChild(line);
                    linesDrawn++;
                    break;
                }
            }
        }
    });
    console.log('[OK] REAL: Total connection lines drawn:', linesDrawn);
}
// Original complex function
function drawComplexMappingLines(container) {
    console.log('🎨 COMPLEX: Starting to draw connection lines for container:', container);
    drawComplexMappingLinesSimple(container);
}
// SYSTEMATIC DEBUGGING: Let's check everything step by step
function debugLineDrawingIssue(container) {
    console.log('📂§ =========================');
    console.log('📂§ SYSTEMATIC DEBUGGING START');
    console.log('📂§ =========================');
    // Step 1: Check container
    console.log('📂§ STEP 1: Container check');
    console.log('📂§ Container element:', container);
    console.log('📂§ Container innerHTML length:', container.innerHTML.length);
    // Step 2: Check SVG
    console.log('📂§ STEP 2: SVG check');
    var svg = container.querySelector('.connection-svg');
    console.log('📂§ SVG found:', !!svg);
    if (svg) {
        console.log('📂§ SVG element:', svg);
        console.log('📂§ SVG style:', svg.style.cssText);
        console.log('📂§ SVG dimensions:', svg.getAttribute('width'), 'x', svg.getAttribute('height'));
        console.log('📂§ SVG position:', svg.getBoundingClientRect());
    }
    // Step 3: Check for mapping elements
    console.log('📂§ STEP 3: Element selector check');
    var mergedHmdItems = container.querySelectorAll('.merged-hmd-item');
    var sourceHmdItems = container.querySelectorAll('.source-hmd-item');
    var mergedVmdItems = container.querySelectorAll('.merged-vmd-item');
    var sourceVmdItems = container.querySelectorAll('.source-vmd-item');
    console.log('📂§ Found merged HMD items:', mergedHmdItems.length);
    console.log('📂§ Found source HMD items:', sourceHmdItems.length);
    console.log('📂§ Found merged VMD items:', mergedVmdItems.length);
    console.log('📂§ Found source VMD items:', sourceVmdItems.length);
    // Step 4: Log actual elements and their positions
    console.log('📂§ STEP 4: Element positions');
    if (mergedHmdItems.length > 0) {
        console.log('📂§ First merged HMD item:', mergedHmdItems[0]);
        console.log('📂§ First merged HMD rect:', mergedHmdItems[0].getBoundingClientRect());
        console.log('📂§ First merged HMD text:', mergedHmdItems[0].textContent);
    }
    if (sourceHmdItems.length > 0) {
        console.log('📂§ First source HMD item:', sourceHmdItems[0]);
        console.log('📂§ First source HMD rect:', sourceHmdItems[0].getBoundingClientRect());
        console.log('📂§ First source HMD text:', sourceHmdItems[0].textContent);
    }
    // Step 5: Try to create a test line
    console.log('📂§ STEP 5: Test line creation');
    if (svg && mergedHmdItems.length > 0 && sourceHmdItems.length > 0) {
        console.log('📂§ Creating test line...');
        var testLine = document.createElementNS('http://www.w3.org/2000/svg', 'line');
        testLine.setAttribute('x1', '100');
        testLine.setAttribute('y1', '50');
        testLine.setAttribute('x2', '300');
        testLine.setAttribute('y2', '50');
        testLine.setAttribute('stroke', 'red');
        testLine.setAttribute('stroke-width', '5');
        svg.appendChild(testLine);
        console.log('📂§ Test line added to SVG');
    }
    console.log('📂§ =========================');
    // console.log('📂§ SYSTEMATIC DEBUGGING END');
    console.log('📂§ =========================');
}
// Actual line drawing function (separated for clarity)
function performLineDrawing(container) {
    console.log('🎨 Performing actual line drawing on container:', container);
    // Run systematic debugging first
    debugLineDrawingIssue(container);
    svg.innerHTML = ''; // Clear existing lines
    var mergedHmdItems = container.querySelectorAll('.merged-hmd-item');
    var sourceHmdItems = container.querySelectorAll('.source-hmd-item');
    var mergedVmdItems = container.querySelectorAll('.merged-vmd-item');
    var sourceVmdItems = container.querySelectorAll('.source-vmd-item');
    console.log('📂 Found elements - Merged HMD:', mergedHmdItems.length, 'Source HMD:', sourceHmdItems.length, 'Merged VMD:', mergedVmdItems.length, 'Source VMD:', sourceVmdItems.length);
    // Get the mapping container for relative positioning
    var mappingContainer = container.querySelector('.mapping-container');
    if (!mappingContainer) {
        console.log('âŒ Mapping container not found');
        return;
    }
    console.log('[OK] Mapping container found and verified');
    // Set SVG dimensions based on actual container measurements (now that elements are visible)
    var containerRect = mappingContainer.getBoundingClientRect();
    var containerWidth = Math.max(containerRect.width, mappingContainer.offsetWidth, 800);
    var containerHeight = Math.max(containerRect.height, mappingContainer.offsetHeight, 400);
    svg.setAttribute('width', containerWidth);
    svg.setAttribute('height', containerHeight);
    svg.style.width = containerWidth + 'px';
    svg.style.height = containerHeight + 'px';
    svg.style.position = 'absolute';
    svg.style.top = '0';
    svg.style.left = '0';
    svg.style.zIndex = '10';
    svg.style.pointerEvents = 'none'; // Allow clicks to pass through
    console.log('🔍 SVG dimensions set to:', containerWidth, 'x', containerHeight);
    console.log('🔍 Container actual dimensions:', containerRect.width, 'x', containerRect.height);
    // Draw HMD connection lines (green) - match merged to source
    console.log('📂µ Starting HMD line drawing...');
    var hmdLinesDrawn = 0;
    mergedHmdItems.forEach(function (mergedItem, index) {
        var mappedValue = mergedItem.getAttribute('data-mapped');
        var mergedAttr = mergedItem.getAttribute('data-attribute');
        console.log('📂 HMD Item ' + index + ':', {
            text: mergedItem.textContent,
            attr: mergedAttr,
            mapped: mappedValue
        });
        if (mappedValue && mappedValue.trim()) {
            // Find the corresponding source item
            var sourceItem = null;
            for (var i = 0; i < sourceHmdItems.length; i++) {
                var sourceAttr = sourceHmdItems[i].getAttribute('data-source');
                var mappedToMerged = sourceHmdItems[i].getAttribute('data-mapped-to');
                console.log('  Checking source item:', {
                    text: sourceHmdItems[i].textContent,
                    sourceAttr: sourceAttr,
                    mappedToMerged: mappedToMerged
                });
                // Match if this source maps to the current merged attribute
                if (mappedToMerged === mergedAttr && sourceAttr && sourceAttr.trim()) {
                    sourceItem = sourceHmdItems[i];
                    console.log('[OK] Found matching source item!');
                    break;
                }
            }
            if (sourceItem && sourceItem.textContent.trim()) {
                console.log('🟢 Drawing HMD line for:', mergedItem.textContent, '->', sourceItem.textContent);
                // Get positions relative to the mapping container (elements are now guaranteed visible)
                var mergedRect = mergedItem.getBoundingClientRect();
                var sourceRect = sourceItem.getBoundingClientRect();
                var containerRect = mappingContainer.getBoundingClientRect();
                // Calculate line coordinates relative to container
                var startX = mergedRect.right - containerRect.left;
                var startY = mergedRect.top + mergedRect.height / 2 - containerRect.top;
                var endX = sourceRect.left - containerRect.left;
                var endY = sourceRect.top + sourceRect.height / 2 - containerRect.top;
                // Ensure coordinates are within SVG bounds
                startX = Math.max(0, Math.min(startX, containerWidth));
                startY = Math.max(0, Math.min(startY, containerHeight));
                endX = Math.max(0, Math.min(endX, containerWidth));
                endY = Math.max(0, Math.min(endY, containerHeight));
                console.log('🟢 HMD Line coordinates:', { startX, startY, endX, endY });
                console.log('  Merged rect:', { x: mergedRect.x, y: mergedRect.y, w: mergedRect.width, h: mergedRect.height });
                console.log('  Source rect:', { x: sourceRect.x, y: sourceRect.y, w: sourceRect.width, h: sourceRect.height });
                console.log('  Container rect:', { x: containerRect.x, y: containerRect.y, w: containerRect.width, h: containerRect.height });
                var line = document.createElementNS('http://www.w3.org/2000/svg', 'line');
                line.setAttribute('x1', startX);
                line.setAttribute('y1', startY);
                line.setAttribute('x2', endX);
                line.setAttribute('y2', endY);
                line.setAttribute('stroke', '#4CAF50');
                line.setAttribute('stroke-width', '3');
                line.setAttribute('opacity', '0.8');
                svg.appendChild(line);
                hmdLinesDrawn++;
                console.log('[OK] HMD Line added to SVG');
            } else {
                console.log('âŒ No matching source item found for:', mergedItem.textContent);
            }
        } else {
            console.log('â­ï¸ Skipping unmapped HMD item:', mergedItem.textContent);
        }
    });
    console.log('🔍 Total HMD lines drawn:', hmdLinesDrawn);
    // Draw VMD connection lines (red) - match merged to source
    console.log('📂´ Starting VMD line drawing...');
    var vmdLinesDrawn = 0;
    mergedVmdItems.forEach(function (mergedItem, index) {
        var mappedValue = mergedItem.getAttribute('data-mapped');
        var mergedAttr = mergedItem.getAttribute('data-attribute');
        console.log('📂 VMD Item ' + index + ':', {
            text: mergedItem.textContent,
            attr: mergedAttr,
            mapped: mappedValue
        });
        if (mappedValue && mappedValue.trim()) {
            // Find the corresponding source item
            var sourceItem = null;
            for (var i = 0; i < sourceVmdItems.length; i++) {
                var sourceAttr = sourceVmdItems[i].getAttribute('data-source');
                var mappedToMerged = sourceVmdItems[i].getAttribute('data-mapped-to');
                // Match if this source maps to the current merged attribute
                if (mappedToMerged === mergedAttr && sourceAttr && sourceAttr.trim()) {
                    sourceItem = sourceVmdItems[i];
                    console.log('[OK] Found matching VMD source item!');
                    break;
                }
            }
            if (sourceItem && sourceItem.textContent.trim()) {
                console.log('📂´ Drawing VMD line for:', mergedItem.textContent, '->', sourceItem.textContent);
                // Get positions relative to the mapping container (elements are now guaranteed visible)
                var mergedRect = mergedItem.getBoundingClientRect();
                var sourceRect = sourceItem.getBoundingClientRect();
                var containerRect = mappingContainer.getBoundingClientRect();
                // Calculate line coordinates relative to container
                var startX = mergedRect.right - containerRect.left;
                var startY = mergedRect.top + mergedRect.height / 2 - containerRect.top;
                var endX = sourceRect.left - containerRect.left;
                var endY = sourceRect.top + sourceRect.height / 2 - containerRect.top;
                // Ensure coordinates are within SVG bounds
                startX = Math.max(0, Math.min(startX, containerWidth));
                startY = Math.max(0, Math.min(startY, containerHeight));
                endX = Math.max(0, Math.min(endX, containerWidth));
                endY = Math.max(0, Math.min(endY, containerHeight));
                console.log('📂´ VMD Line coordinates:', { startX, startY, endX, endY });
                console.log('  Merged rect:', { x: mergedRect.x, y: mergedRect.y, w: mergedRect.width, h: mergedRect.height });
                console.log('  Source rect:', { x: sourceRect.x, y: sourceRect.y, w: sourceRect.width, h: sourceRect.height });
                var line = document.createElementNS('http://www.w3.org/2000/svg', 'line');
                line.setAttribute('x1', startX);
                line.setAttribute('y1', startY);
                line.setAttribute('x2', endX);
                line.setAttribute('y2', endY);
                line.setAttribute('stroke', '#f44336');
                line.setAttribute('stroke-width', '3');
                line.setAttribute('opacity', '0.8');
                svg.appendChild(line);
                vmdLinesDrawn++;
                console.log('[OK] VMD Line added to SVG');
            } else {
                console.log('âŒ No matching VMD source item found for:', mergedItem.textContent);
            }
        } else {
            console.log('â­ï¸ Skipping unmapped VMD item:', mergedItem.textContent);
        }
    });
    console.log('🔍 Total VMD lines drawn:', vmdLinesDrawn);
    console.log('🎨 Connection line drawing completed. Total lines:', (hmdLinesDrawn + vmdLinesDrawn));
}
// Function to create simple side-by-side mapping table
function createSimpleMappingTable(hmdMappings, vmdMappings, title) {
    var html = '<div style="background: white; border-radius: 8px; padding: 20px; box-shadow: 0 2px 8px rgba(0,0,0,0.1); margin: 10px;">';
    html += '<h3 style="text-align: center; color: #333; margin-bottom: 20px; font-weight: bold;">' + title + '</h3>';
    html += '<div style="display: flex; gap: 20px; justify-content: space-between;">';
    // HMD Mappings column
    html += '<div style="flex: 1;">';
    html += '<h4 style="color: #2E7D32; text-align: center; margin-bottom: 15px; padding: 8px; background: #e8f5e9; border-radius: 6px;">HMD Mappings (' + hmdMappings.length + ')</h4>';
    if (hmdMappings.length > 0) {
        html += '<table style="width: 100%; border-collapse: collapse; border: 1px solid #ddd;">';
        html += '<thead><tr style="background: #f5f5f5;"><th style="border: 1px solid #ddd; padding: 8px; text-align: left;">Source</th><th style="border: 1px solid #ddd; padding: 8px; text-align: left;">Target</th></tr></thead>';
        html += '<tbody>';
        hmdMappings.forEach(function (mapping) {
            var sourceValue, targetValue;
            // Handle different mapping formats
            if (mapping.source && mapping.target) {
                // Simple table format
                sourceValue = mapping.source;
                targetValue = mapping.target;
            } else if (mapping.merged && (mapping.t1 || mapping.t2 || mapping.source1 || mapping.source2)) {
                // Complex table format for merged schemas
                targetValue = mapping.merged;
                sourceValue = mapping.t1 || mapping.t2 || mapping.source1 || mapping.source2;
            } else {
                // Fallback
                sourceValue = mapping.source || mapping.t1 || mapping.t2 || mapping.source1 || mapping.source2 || 'Unknown';
                targetValue = mapping.target || mapping.merged || 'Unknown';
            }
            html += '<tr>';
            html += '<td style="border: 1px solid #ddd; padding: 8px;">' + sourceValue + '</td>';
            html += '<td style="border: 1px solid #ddd; padding: 8px;">' + targetValue + '</td>';
            html += '</tr>';
        });
        html += '</tbody></table>';
    } else {
        html += '<div style="text-align: center; color: #666; font-style: italic; padding: 20px;">No HMD mappings found</div>';
    }
    html += '</div>';
    // VMD Mappings column
    html += '<div style="flex: 1;">';
    html += '<h4 style="color: #c62828; text-align: center; margin-bottom: 15px; padding: 8px; background: #ffebee; border-radius: 6px;">VMD Mappings (' + vmdMappings.length + ')</h4>';
    if (vmdMappings.length > 0) {
        html += '<table style="width: 100%; border-collapse: collapse; border: 1px solid #ddd;">';
        html += '<thead><tr style="background: #f5f5f5;"><th style="border: 1px solid #ddd; padding: 8px; text-align: left;">Source</th><th style="border: 1px solid #ddd; padding: 8px; text-align: left;">Target</th></tr></thead>';
        html += '<tbody>';
        vmdMappings.forEach(function (mapping) {
            var sourceValue, targetValue;
            // Handle different mapping formats
            if (mapping.source && mapping.target) {
                // Simple table format
                sourceValue = mapping.source;
                targetValue = mapping.target;
            } else if (mapping.merged && (mapping.t1 || mapping.t2 || mapping.source1 || mapping.source2)) {
                // Complex table format for merged schemas
                targetValue = mapping.merged;
                sourceValue = mapping.t1 || mapping.t2 || mapping.source1 || mapping.source2;
            } else {
                // Fallback
                sourceValue = mapping.source || mapping.t1 || mapping.t2 || mapping.source1 || mapping.source2 || 'Unknown';
                targetValue = mapping.target || mapping.merged || 'Unknown';
            }
            html += '<tr>';
            html += '<td style="border: 1px solid #ddd; padding: 8px;">' + sourceValue + '</td>';
            html += '<td style="border: 1px solid #ddd; padding: 8px;">' + targetValue + '</td>';
            html += '</tr>';
        });
        html += '</tbody></table>';
    } else {
        html += '<div style="text-align: center; color: #666; font-style: italic; padding: 20px;">No VMD mappings found</div>';
    }
    html += '</div>';
    html += '</div>';
    html += '</div>';
    return html;
}
// Function to draw connection lines for merged schema mappings
function drawMergedConnectionLines(overlayId, hmdMappings, vmdMappings, sourceType, targetType) {
    console.log('[AUTO] Starting merged connection lines drawing:', {
        overlayId,
        hmdCount: hmdMappings ? hmdMappings.length : 0,
        vmdCount: vmdMappings ? vmdMappings.length : 0,
        sourceType,
        targetType
    });
    var svg = document.getElementById(overlayId);
    if (!svg) {
        console.error('âŒ SVG overlay not found:', overlayId);
        return;
    }
    console.log('[OK] SVG found:', svg);
    svg.innerHTML = '';
    var container = svg.closest('.mapping-tables-container');
    if (!container) {
        console.error('âŒ Container not found for SVG');
        return;
    }
    console.log('[OK] Container found:', container);
    var rect = container.getBoundingClientRect();
    console.log('🔍 Container rect:', rect);
    // Check if container has valid dimensions
    if (rect.width === 0 || rect.height === 0) {
        console.warn('[WARNING] Container has zero dimensions, retrying in 500ms...');
        setTimeout(function () {
            drawMergedConnectionLines(overlayId, hmdMappings, vmdMappings, sourceType, targetType);
        }, 500);
        return;
    }
    // Set larger viewBox for new layout with absolute positioning
    const viewBoxWidth = Math.max(rect.width, 1200); // Ensure enough width for both tables
    const viewBoxHeight = Math.max(rect.height, 700); // Ensure enough height for vertical offset
    svg.setAttribute('viewBox', '0 0 ' + viewBoxWidth + ' ' + viewBoxHeight);
    console.log('🔍 SVG viewBox set:', viewBoxWidth + 'x' + viewBoxHeight);
    // Draw HMD connections using the professional style (same as main schema mapping)
    if (hmdMappings && hmdMappings.length > 0) {
        console.log('🟢 Drawing HMD connections with professional style:', hmdMappings);
        drawMergedHmdConnections(svg, hmdMappings, rect, sourceType, targetType);
    } else {
        console.log('âšª No HMD mappings to draw');
    }
    // Draw VMD connections using the professional style (same as main schema mapping)
    if (vmdMappings && vmdMappings.length > 0) {
        console.log('📂´ Drawing VMD connections with professional style:', vmdMappings);
        drawMergedVmdConnections(svg, vmdMappings, rect, sourceType, targetType);
    } else {
        console.log('âšª No VMD mappings to draw');
    }
    console.log('🎉 Finished drawing merged connections with professional style');
}
// Professional HMD connections for merged schemas
function drawMergedHmdConnections(svg, hmdMappings, rect, sourceType, targetType) {
    console.log('🟢 drawMergedHmdConnections called with:', {
        mappingCount: hmdMappings ? hmdMappings.length : 0,
        mappings: hmdMappings,
        sourceType,
        targetType
    });
    if (!Array.isArray(hmdMappings) || !hmdMappings.length) {
        console.log('âŒ No HMD mappings to draw');
        return;
    }
    // Check if we're in a vertical layout (merged tabs)
    const container = svg.closest('.mapping-tables-container');
    const isVerticalLayout = container && (
        container.closest('#merged-source-tab') ||
        container.closest('#merged-target-tab')
    );
    // Adjust routing for vertical layout
    const laneSpacing = 25;
    const firstLaneY = isVerticalLayout ? 50 : 80; // Higher for vertical layout
    const minDistanceAbove = isVerticalLayout ? 30 : 40;
    hmdMappings.forEach((mapping, index) => {
        // Handle both old format (source/target) and new format (merged/t1/t2)
        const sourceField = mapping.merged || mapping.source || '';
        const targetField = mapping.t1 || mapping.t2 || mapping.source1 || mapping.source2 || mapping.target || '';
        const sourceAttr = (sourceField || '').toString().replace('HMD_Merged_Schema.', '').replace('Merged_Schema.', '');
        const targetAttr = (targetField || '').toString().replace('Table1.HMD.', '').replace('Table2.HMD.', '').replace('Schema1.', '').replace('Schema2.', '');
        console.log(`📂 Processing HMD mapping ${index + 1}:`, {
            sourceField, targetField, sourceAttr, targetAttr
        });
        const srcEl = _findMergedElement(sourceType, 'header', sourceAttr);
        const tgtEl = _findMergedElement(targetType, 'header', targetAttr);
        if (!srcEl || !tgtEl) {
            console.warn('âŒ Could not find merged HMD elements:', {
                sourceAttr, targetAttr,
                srcEl: !!srcEl,
                tgtEl: !!tgtEl
            });
            return;
        }
        console.log('[OK] Found HMD elements, drawing connection');
        const srcBounds = srcEl.getBoundingClientRect();
        const tgtBounds = tgtEl.getBoundingClientRect();
        // Calculate relative positions within the container
        const containerBounds = container.getBoundingClientRect();
        let startX = srcBounds.left + srcBounds.width / 2 - containerBounds.left;
        let startY = srcBounds.top - containerBounds.top;
        let endX = tgtBounds.left + tgtBounds.width / 2 - containerBounds.left;
        let endY = tgtBounds.top - containerBounds.top;
        console.log('HMD Connection coordinates:', {
            sourceField: mapping.merged || mapping.source,
            targetField: mapping.t1 || mapping.t2 || mapping.source1 || mapping.source2 || mapping.target,
            startX, startY, endX, endY
        });
        // Professional routing: above tables with proper lane separation
        const laneY = firstLaneY - (index * laneSpacing);
        // Find the top of both tables to ensure we stay well above them
        const sourceTableTop = srcBounds.top - rect.top;
        const targetTableTop = tgtBounds.top - rect.top;
        const tablesTop = Math.min(sourceTableTop, targetTableTop);
        // Calculate the minimum safe Y position for this specific lane
        const minSafeY = tablesTop - minDistanceAbove - (index * laneSpacing);
        // Use the higher position (more negative Y = higher on screen)
        const routingY = Math.min(laneY, minSafeY); // Each lane maintains its individual offset
        console.log(`🟢 HMD mapping ${index}:`, {
            lane: index,
            laneY: laneY,
            minSafeY: minSafeY,
            routingY: routingY,
            tablesTop: tablesTop,
            finalDifference: routingY - (index > 0 ? (firstLaneY - ((index - 1) * laneSpacing)) : firstLaneY)
        });
        // Use complex routing only for vertical layout (merged tabs)
        let path;
        if (isVerticalLayout) {
            // Find the actual merge table to calculate proper clearance
            const mergeTable = container.querySelector('.source-table-container table');
            const mergeTableBounds = mergeTable ? mergeTable.getBoundingClientRect() : srcBounds;
            // Calculate positions relative to container
            const mergeTableTop = mergeTableBounds.top - containerBounds.top;
            const mergeTableRight = mergeTableBounds.right - containerBounds.left;
            const mergeTableBottom = mergeTableBounds.bottom - containerBounds.top;
            // Pop up WELL ABOVE the merge table top, each line at different height
            const minClearanceAbove = 40; // Minimum distance above table
            const lineSpacing = 25; // Space between each HMD line
            const popUpY = mergeTableTop - minClearanceAbove - (index * lineSpacing);
            // Go right PAST the merge table right edge with minimal clearance
            const rightClearance = 30;
            const rightX = mergeTableRight + rightClearance;
            // Each line turns down at different X position but minimize extension
            const downX = mergeTableRight + rightClearance - (index * 10);
            // Turn down to a point between the tables, each at different Y level
            const betweenY = mergeTableBottom + 15 + (index * 8);
            // Go directly to target X position (no separate enter position)
            const targetX = tgtBounds.left + tgtBounds.width / 2 - containerBounds.left;
            const targetY = tgtBounds.top + tgtBounds.height / 2 - containerBounds.top;
            // Start exactly from the attribute header center (middle of header)
            const actualStartX = srcBounds.left + srcBounds.width / 2 - containerBounds.left;
            const actualStartY = srcBounds.top + srcBounds.height / 2 - containerBounds.top;
            path = `M ${actualStartX} ${actualStartY} ` +    // Start exactly at attribute
                `L ${actualStartX} ${popUpY} ` +          // Pop up well above merge table
                `L ${downX} ${popUpY} ` +                 // Go right just past merge table (no extra extension)
                `L ${downX} ${betweenY} ` +               // Turn down (separated lines)
                `L ${targetX} ${betweenY} ` +             // Go left directly to target X
                `L ${targetX} ${targetY}`;                // Go straight down to target attribute
        } else {
            // Simple routing for other tabs (original behavior)
            path = `M ${startX} ${startY} ` +
                `L ${startX} ${routingY} ` +
                `L ${endX} ${routingY} ` +
                `L ${endX} ${endY}`;
        }
        // Use professional green color and styling
        _drawPath(svg, path, '#66bb6a', 3, 0.95);
        _drawConnectionIndicator(svg, startX, startY, '#66bb6a');
        _drawConnectionIndicator(svg, endX, endY, '#66bb6a');
    });
}
// Professional VMD connections for merged schemas
function drawMergedVmdConnections(svg, vmdMappings, rect, sourceType, targetType) {
    console.log('📂´ drawMergedVmdConnections called with:', {
        mappingCount: vmdMappings ? vmdMappings.length : 0,
        mappings: vmdMappings,
        sourceType,
        targetType
    });
    if (!Array.isArray(vmdMappings) || !vmdMappings.length) {
        console.log('âŒ No VMD mappings to draw');
        return;
    }
    // Check if we're in a vertical layout (merged tabs)
    const container = svg.closest('.mapping-tables-container');
    const isVerticalLayout = container && (
        container.closest('#merged-source-tab') ||
        container.closest('#merged-target-tab')
    );
    // Adjust routing for vertical layout
    const leftMargin = isVerticalLayout ? 30 : 50; // Smaller margin for vertical layout
    const bottomMargin = isVerticalLayout ? 20 : 40;
    const laneSpacing = 15;
    vmdMappings.forEach((mapping, index) => {
        // Handle both old format (source/target) and new format (merged/t1/t2)
        const sourceField = mapping.merged || mapping.source || '';
        const targetField = mapping.t1 || mapping.t2 || mapping.source1 || mapping.source2 || mapping.target || '';
        const sourceAttr = (sourceField || '').toString().replace('VMD_Merged_Schema.', '').replace('Merged_Schema.', '');
        const targetAttr = (targetField || '').toString().replace('Table1.VMD.', '').replace('Table2.VMD.', '').replace('Schema1.', '').replace('Schema2.', '');
        const sourceRow = _findMergedElement(sourceType, 'row', sourceAttr);
        const targetRow = _findMergedElement(targetType, 'row', targetAttr);
        if (!sourceRow || !targetRow) {
            console.warn('Could not find merged VMD elements:', { sourceAttr, targetAttr });
            return;
        }
        const sourceRowRect = sourceRow.getBoundingClientRect();
        const targetRowRect = targetRow.getBoundingClientRect();
        // Professional left routing pattern - use container bounds for consistency
        const containerBounds = container.getBoundingClientRect();
        // Start exactly from row edge (right side of source table)
        const sourceX = sourceRowRect.right - containerBounds.left;
        const sourceY = (sourceRowRect.top + sourceRowRect.height / 2) - containerBounds.top;
        // End exactly at row edge (left side of target table)  
        const targetX = targetRowRect.left - containerBounds.left;
        const targetY = (targetRowRect.top + targetRowRect.height / 2) - containerBounds.top;
        console.log('VMD Connection coordinates:', {
            sourceField: mapping.merged || mapping.source,
            targetField: mapping.t1 || mapping.t2 || mapping.source1 || mapping.source2 || mapping.target,
            sourceY, targetY
        });
        const sourceLeftX = sourceRowRect.left - containerBounds.left;
        const targetLeftX = targetRowRect.left - containerBounds.left;
        // Add horizontal offset for each VMD mapping to prevent overlapping routes
        const horizontalOffset = index * 20; // Each mapping gets its own horizontal lane
        const leftRoutingX = sourceLeftX - leftMargin - horizontalOffset;
        // Find the bottom-most point of BOTH tables to ensure we go below everything
        const sourceTableEl = _findMergedElement(sourceType, 'table', '');
        const targetTableEl = _findMergedElement(targetType, 'table', '');
        let tablesBottom = Math.max(sourceRowRect.bottom, targetRowRect.bottom);
        if (sourceTableEl) {
            const sourceTableRect = sourceTableEl.getBoundingClientRect();
            tablesBottom = Math.max(tablesBottom, sourceTableRect.bottom);
        }
        if (targetTableEl) {
            const targetTableRect = targetTableEl.getBoundingClientRect();
            tablesBottom = Math.max(tablesBottom, targetTableRect.bottom);
        }
        // Optimized: turn right immediately below table with minimal spacing
        const baseClearance = 20; // Minimal space below table (turn right immediately)
        const progressiveSpacing = 15; // Small additional space for each subsequent mapping
        // Turn right immediately below table with just enough offset for separation
        const routingBottom = tablesBottom - rect.top + baseClearance + (index * progressiveSpacing);
        console.log(`📂´ VMD mapping ${index}: routing at Y=${routingBottom} (${baseClearance + (index * progressiveSpacing)}px below tables)`);
        // Calculate the right routing X - add margin before the target VMD row + horizontal offset
        const rightMargin = 30; // Space before reaching the target VMD
        const rightRoutingX = targetLeftX - rightMargin + horizontalOffset; // Mirror the left offset
        // Check if we're in vertical layout (merged tabs)
        const isVerticalLayout = container && (
            container.closest('#merged-source-tab') ||
            container.closest('#merged-target-tab')
        );
        let path;
        if (isVerticalLayout) {
            // For vertical layout: LEFT edge to LEFT edge (as shown in current5.png)
            const startX = sourceRowRect.left - containerBounds.left;   // LEFT edge of merge table row
            const startY = (sourceRowRect.top + sourceRowRect.height / 2) - containerBounds.top;
            const endX = targetRowRect.left - containerBounds.left;     // LEFT edge of target table row  
            const endY = (targetRowRect.top + targetRowRect.height / 2) - containerBounds.top;
            // Direct connection from left edge to left edge
            path = `M ${startX} ${startY} L ${endX} ${endY}`;
        } else {
            // Professional left → down (below table) → right → up → right → final right routing
            path = `M ${sourceLeftX} ${sourceY} ` +                     // Start at source row
                `L ${leftRoutingX} ${sourceY} ` +                      // Go LEFT 
                `L ${leftRoutingX} ${routingBottom} ` +                // Go DOWN below all tables
                `L ${rightRoutingX} ${routingBottom} ` +               // Go RIGHT across (below tables)
                `L ${rightRoutingX} ${targetY} ` +                     // Go UP to target level
                `L ${targetLeftX} ${targetY}`;                        // Final RIGHT turn to VMD row
        }
        // Use different colors for variety (same as main mapping)
        const colors = ['#e57373', '#f06292', '#ba68c8', '#9575cd', '#7986cb'];
        const color = colors[index % colors.length];
        _drawPath(svg, path, color, 2.5, 0.9);
        _drawConnectionIndicator(svg, sourceLeftX, sourceY, color);
        _drawConnectionIndicator(svg, targetLeftX, targetY, color);
    });
}
// Helper function to find elements in merged schema context
function _findMergedElement(side, dataAttr, value) {
    var containerId;
    if (side === 'merged') {
        containerId = 'mergedSchemaDisplay';
    } else if (side === 'merged2') {
        containerId = 'mergedSchemaDisplay2';
    } else if (side === 'source-from-merged') {
        containerId = 'sourceSchemaDisplay';
    } else if (side === 'target-from-merged') {
        containerId = 'targetSchemaDisplay';
    } else {
        return null;
    }
    const root = document.getElementById(containerId);
    if (!root) {
        console.warn(`Could not find root element for merged ${side} side`);
        return null;
    }
    // Special case: if looking for table, return the table element directly
    if (dataAttr === 'table') {
        return root.querySelector('table');
    }
    const cleanValue = String(value).trim();
    // Try direct attribute match first
    let element = root.querySelector(`[data-${dataAttr}="${cleanValue}"]`);
    if (!element) {
        // Try fuzzy matching
        if (dataAttr === 'header') {
            element = _findHeaderFuzzy(root, cleanValue);
        } else if (dataAttr === 'row') {
            element = _findRowFuzzyWithVMD(root, cleanValue);
        }
    }
    if (!element) {
        console.warn(`Could not find merged element with data-${dataAttr}="${cleanValue}" on ${side} side`);
    }
    return element;
}
function drawSimpleLinesByIndex(pairs) {
    var svg = document.getElementById('connectionOverlay');
    if (!svg) return;
    svg.innerHTML = '';
    var container = document.querySelector('.mapping-tables-container');
    if (!container) return;
    var rect = container.getBoundingClientRect();
    svg.setAttribute('viewBox', '0 0 ' + rect.width + ' ' + rect.height);
    pairs.forEach(function (_m, i) {
        var src = document.querySelector('[data-side="source"][data-idx="' + i + '"]');
        var tgt = document.querySelector('[data-side="target"][data-idx="' + i + '"]');
        if (!src || !tgt) return;
        var s = src.getBoundingClientRect();
        var t = tgt.getBoundingClientRect();
        var startX = s.right - rect.left;
        var startY = s.top + s.height / 2 - rect.top;
        var endX = t.left - rect.left;
        var endY = t.top + t.height / 2 - rect.top;
        var midX = (startX + endX) / 2;
        var d = 'M ' + startX + ' ' + startY +
            ' Q ' + midX + ' ' + startY + ' ' + midX + ' ' + ((startY + endY) / 2) +
            ' Q ' + midX + ' ' + endY + ' ' + endX + ' ' + endY;
        var path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
        path.setAttribute('d', d);
        path.setAttribute('stroke', '#4CAF50');
        path.setAttribute('stroke-width', '2');
        path.setAttribute('fill', 'none');
        path.setAttribute('opacity', '0.9');
        svg.appendChild(path);
    });
}
// Utils
function showLoading(show) {
    document.getElementById('loading').classList.toggle('active', show);
}
function showError(msg) {
    var e = document.getElementById('error');
    e.textContent = msg;
    e.style.display = 'block';
    setTimeout(function () { e.style.display = 'none'; }, 5000);
}
function showSuccess(msg) {
    var s = document.getElementById('success');
    s.textContent = msg;
    s.style.display = 'block';
    setTimeout(function () { s.style.display = 'none'; }, 3000);
}
function hideMessages() {
    document.getElementById('error').style.display = 'none';
    document.getElementById('success').style.display = 'none';
}
// Display metrics in a comprehensive grid layout
function displayMetrics(metrics) {
    const metricsContainer = document.getElementById('metricsDisplay');
    if (!metricsContainer) return;
    if (!metrics) {
        metricsContainer.innerHTML = `
    <div style="text-align:center;color:#666;">
        No metrics available yet. Process schemas to see performance data.
    </div>
`;
        return;
    }
    const metricsGrid = document.createElement('div');
    metricsGrid.style.cssText = `
display: grid;
grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
gap: 20px;
margin-top: 20px;
    `;
    // Cost formatting function
    function formatCostDisplay(cost) {
        if (!cost || cost === 0) return '$0.00';
        if (cost < 0.000001) return '$' + cost.toFixed(8);
        if (cost < 0.0001) return '$' + cost.toFixed(6);
        if (cost < 0.01) return '$' + cost.toFixed(4);
        return '$' + cost.toFixed(2);
    }

    // Handle partition pipeline with 3 distinct phases
    const isPartitionPipeline = metrics.operation_type === 'partition_pipeline';

    // Handle both old format (for compatibility) and new flexible pipeline format
    const isNewFormat = metrics.matching_time !== undefined || metrics.merge_time !== undefined;
    let metricCards = [];

    if (isPartitionPipeline) {
        // Special 3-phase partition pipeline format
        metricCards = [
            // Summary row
            { title: 'Pipeline Type', value: 'Match + Merge', label: 'Operation Mode', color: '#4CAF50' },
            { title: 'Pipeline Config', value: metrics.pipeline_description || 'N/A', label: 'Full Pipeline Configuration', color: '#673AB7' },
            { title: 'Total Time', value: `${(metrics.total_generation_time || 0).toFixed(2)}s`, label: 'Processing Duration', color: '#4CAF50' },
            { title: 'Tokens/Second', value: (metrics.tokens_per_second || 0).toFixed(1), label: 'Generation Speed', color: '#9C27B0' },
            { title: 'Total Cost', value: formatCostDisplay(metrics.api_call_cost || 0), label: 'Combined Cost', color: '#E91E63' },

            // Phase 1: Match
            { title: 'Match LLM', value: metrics.matching_llm_used || 'N/A', label: 'Phase 1 Model', color: '#2196F3' },
            { title: 'Match Time', value: `${(metrics.match_generation_time || 0).toFixed(2)}s`, label: 'Schema Matching', color: '#2196F3' },
            { title: 'Match Input', value: metrics.match_input_tokens || 0, label: 'Match Prompt Tokens', color: '#607D8B' },
            { title: 'Match Output', value: metrics.match_output_tokens || 0, label: 'Match Response Tokens', color: '#795548' },
            { title: 'Match Cost', value: formatCostDisplay(metrics.match_api_cost || 0), label: 'Matching Cost', color: '#2196F3' },

            // Phase 2: Schema Merge
            { title: 'Schema Merge LLM', value: metrics.merge_llm_used || 'N/A', label: 'Phase 2 Model', color: '#FF9800' },
            { title: 'Schema Merge Time', value: `${(metrics.schema_merge_generation_time || 0).toFixed(2)}s`, label: 'Schema Merging', color: '#FF9800' },
            { title: 'Schema Merge Input', value: metrics.schema_merge_input_tokens || 0, label: 'Merge Prompt Tokens', color: '#607D8B' },
            { title: 'Schema Merge Output', value: metrics.schema_merge_output_tokens || 0, label: 'Merge Response Tokens', color: '#795548' },
            { title: 'Schema Merge Cost', value: formatCostDisplay(metrics.schema_merge_api_cost || 0), label: 'Schema Merge Cost', color: '#FF9800' },

            // Phase 4: Partition Merge
            { title: 'Partition LLM', value: metrics.partition_llm_used || 'N/A', label: 'Phase 4 Model', color: '#9C27B0' },
            { title: 'Partition Time', value: `${(metrics.partition_merge_generation_time || 0).toFixed(2)}s`, label: `${metrics.total_partitions || 0} Partition Merges`, color: '#9C27B0' },
            { title: 'Partition Input', value: metrics.partition_merge_input_tokens || 0, label: 'Partition Prompt Tokens', color: '#607D8B' },
            { title: 'Partition Output', value: metrics.partition_merge_output_tokens || 0, label: 'Partition Response Tokens', color: '#795548' },
            { title: 'Partition Cost', value: formatCostDisplay(metrics.partition_merge_api_cost || 0), label: 'Partition Merge Cost', color: '#9C27B0' }
        ];
    } else if (isNewFormat) {
        // New flexible pipeline format (currently unused since we reverted to working backend)
        metricCards = [
            { title: 'Total Time', value: `${(metrics.total_time || 0).toFixed(2)}s`, label: 'Pipeline Duration', color: '#4CAF50' },
            { title: 'Input Tokens', value: metrics.input_prompt_tokens || 0, label: 'Prompt Tokens', color: '#607D8B' },
            { title: 'Output Tokens', value: metrics.output_tokens || 0, label: 'Response Tokens', color: '#795548' },
            { title: 'API Cost', value: formatCostDisplay(metrics.cost || 0), label: 'Processing Cost', color: '#E91E63' }
        ];
        // Add step-specific metrics
        if (metrics.matching_time > 0) {
            metricCards.push({
                title: 'Matching Time',
                value: `${(metrics.matching_time || 0).toFixed(2)}s`,
                label: 'Schema Matching',
                color: '#2196F3'
            });
        }
        if (metrics.merge_time > 0) {
            metricCards.push({
                title: 'Merge Time',
                value: `${(metrics.merge_time || 0).toFixed(2)}s`,
                label: 'Schema Merging',
                color: '#FF9800'
            });
        }
    } else {
        // Working backend format
        var pipelineType = metrics.operation_type === 'match' ? 'Match Only' : 'Match + Merge';
        var pipelineColor = metrics.operation_type === 'match' ? '#2196F3' : '#4CAF50';
        // Check if this is a cross-mixing scenario (different LLMs for match and merge)
        // console.log('[DEBUG] Full metrics object:', metrics);
        // console.log('[DEBUG] Metrics data for cross-mixing check:', {
        //     operation_type: metrics.operation_type,
        //     matching_llm_used: metrics.matching_llm_used,
        //     merge_llm_used: metrics.merge_llm_used,
        //     match_input_tokens: metrics.match_input_tokens,
        //     merge_input_tokens: metrics.merge_input_tokens,
        //     match_output_tokens: metrics.match_output_tokens,
        //     merge_output_tokens: metrics.merge_output_tokens
        // });
        const isCrossMixing = (metrics.operation_type === 'merge' || metrics.operation_type === 'instance_merge') &&
            metrics.matching_llm_used &&
            metrics.merge_llm_used &&
            metrics.matching_llm_used !== metrics.merge_llm_used;
        // Check if we have separate token metrics for detailed view (for both cross-mixing and same-LLM scenarios)
        // Show detailed metrics if we have a merge operation with LLM info, even if some token counts are missing
        const hasDetailedMetrics = (metrics.operation_type === 'merge' || metrics.operation_type === 'instance_merge') &&
            (metrics.matching_llm_used && metrics.merge_llm_used) &&
            (metrics.match_input_tokens !== undefined ||
                metrics.merge_input_tokens !== undefined ||
                metrics.match_output_tokens !== undefined ||
                metrics.merge_output_tokens !== undefined);
        // console.log('[DEBUG] Cross-mixing detected:', isCrossMixing);
        // console.log('[DEBUG] Has detailed metrics:', hasDetailedMetrics);
        // console.log('[DEBUG] Metrics object:', {
        //     operation_type: metrics.operation_type,
        //     matching_llm_used: metrics.matching_llm_used,
        //     merge_llm_used: metrics.merge_llm_used,
        //     match_input_tokens: metrics.match_input_tokens,
        //     merge_input_tokens: metrics.merge_input_tokens,
        //     match_output_tokens: metrics.match_output_tokens,
        //     merge_output_tokens: metrics.merge_output_tokens
        // });
        if (hasDetailedMetrics) {
            // Detailed pipeline metrics: Show separate metrics for each step
            metricCards = [
                { title: 'Pipeline Type', value: pipelineType, label: 'Operation Mode', color: pipelineColor },
                { title: 'Pipeline Config', value: metrics.pipeline_description || 'N/A', label: 'Full Pipeline Configuration', color: '#673AB7' },
                { title: 'Total Time', value: `${(metrics.total_generation_time || 0).toFixed(4)}s`, label: 'Processing Duration', color: '#4CAF50' },
                { title: 'Tokens/Second', value: (metrics.tokens_per_second || 0).toFixed(1), label: 'Generation Speed', color: '#9C27B0' },
                { title: 'Total Cost', value: `${formatCostDisplay(metrics.api_call_cost || 0)}`, label: 'Combined Cost', color: '#E91E63' }
            ];
            // Match step metrics
            metricCards.push(
                { title: 'Match LLM', value: metrics.matching_llm_used || 'N/A', label: 'Matching Model', color: '#2196F3' },
                { title: 'Match Time', value: `${(metrics.match_generation_time || 0).toFixed(4)}s`, label: 'Schema Matching', color: '#2196F3' },
                { title: 'Match Input', value: metrics.match_input_tokens || 0, label: 'Match Prompt Tokens', color: '#607D8B' },
                { title: 'Match Output', value: metrics.match_output_tokens || 0, label: 'Match Response Tokens', color: '#795548' },
                { title: 'Match Cost', value: formatCostDisplay(metrics.match_api_cost || 0), label: 'Matching Cost', color: '#2196F3' }
            );
            // Merge step metrics
            metricCards.push(
                { title: 'Merge LLM', value: metrics.merge_llm_used || 'N/A', label: 'Merging Model', color: '#FF9800' },
                { title: 'Merge Time', value: `${(metrics.merge_generation_time || 0).toFixed(4)}s`, label: 'Schema Merging', color: '#FF9800' },
                { title: 'Merge Input', value: metrics.merge_input_tokens || 0, label: 'Merge Prompt Tokens', color: '#607D8B' },
                { title: 'Merge Output', value: metrics.merge_output_tokens || 0, label: 'Merge Response Tokens', color: '#795548' },
                { title: 'Merge Cost', value: formatCostDisplay(metrics.merge_api_cost || 0), label: 'Merging Cost', color: '#FF9800' }
            );
        } else {
            // Single LLM scenario: Show traditional aggregated metrics
            metricCards = [
                { title: 'Pipeline Type', value: pipelineType, label: 'Operation Mode', color: pipelineColor },
                { title: 'Pipeline Config', value: metrics.pipeline_description || 'N/A', label: 'Full Pipeline Configuration', color: '#673AB7' },
                { title: 'LLM Model', value: metrics.llm_model || metrics.matching_llm_used || 'N/A', label: 'AI Model Used', color: '#667eea' },
                { title: 'Total Time', value: `${metrics.total_generation_time || 0}s`, label: 'Processing Duration', color: '#4CAF50' },
                { title: 'Tokens/Second', value: (metrics.tokens_per_second || 0).toFixed(1), label: 'Generation Speed', color: '#9C27B0' },
                { title: 'Input Tokens', value: metrics.input_prompt_tokens || 0, label: 'Prompt Tokens', color: '#607D8B' },
                { title: 'Output Tokens', value: metrics.output_tokens || 0, label: 'Response Tokens', color: '#795548' },
                { title: 'API Cost', value: `${formatCostDisplay(metrics.api_call_cost || 0)}`, label: 'Processing Cost', color: '#E91E63' }
            ];
            // Add step-specific timing for single-LLM merge operations
            if ((metrics.operation_type === 'merge' || metrics.operation_type === 'instance_merge') && (metrics.match_generation_time > 0 || metrics.merge_generation_time > 0)) {
                metricCards.push(
                    { title: 'Match Time', value: `${metrics.match_generation_time || 0}s`, label: 'Schema Matching', color: '#2196F3' },
                    { title: 'Merge Time', value: `${metrics.merge_generation_time || 0}s`, label: 'Schema Merging', color: '#FF9800' }
                );
            }
        }
        // (Duplicate logic removed - already handled above)
    }
    // Add schema-specific metrics
    if (metrics.schema_type === 'complex') {
        metricCards.push(
            { title: 'HMD Matches', value: metrics.hmd_matches || 0, label: 'Header Mappings', color: '#4CAF50' },
            { title: 'VMD Matches', value: metrics.vmd_matches || 0, label: 'Row Mappings', color: '#F44336' }
        );
    }
    metricCards.push(
        { title: 'Total Matches', value: metrics.total_matches || 0, label: 'All Mappings', color: '#FF5722' },
        { title: 'Operation', value: `${metrics.schema_type || 'N/A'} ${metrics.processing_type || 'N/A'} ${metrics.operation_type || 'N/A'}`, label: 'Processing Mode', color: '#795548' },
        { title: 'Session ID', value: (metrics.script_id || 'N/A').split('-')[0], label: 'Unique Identifier', color: '#9E9E9E' }
    );
    metricCards.forEach(metric => {
        const card = document.createElement('div');
        card.style.cssText = `
    background: linear-gradient(135deg, #f8f9fa 0%, #e9ecef 100%);
    padding: 20px;
    border-radius: 10px;
    border-left: 4px solid ${metric.color};
    box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    transition: transform 0.2s ease;
`;
        card.onmouseenter = () => card.style.transform = 'translateY(-2px)';
        card.onmouseleave = () => card.style.transform = 'translateY(0)';
        card.innerHTML = `
    <h4 style="margin: 0 0 10px 0; color: #333; font-size: 14px; text-transform: uppercase; letter-spacing: 0.5px;">${metric.title}</h4>
    <div style="font-size: 24px; font-weight: bold; color: ${metric.color}; margin-bottom: 5px;">${metric.value}</div>
    <div style="font-size: 13px; color: #666;">${metric.label}</div>
`;
        metricsGrid.appendChild(card);
    });
    metricsContainer.innerHTML = '';
    metricsContainer.appendChild(metricsGrid);
}
// Handle tab switching with metrics support
function switchTab(tabName) {
    Array.prototype.forEach.call(document.querySelectorAll('.tab-content'), function (t) {
        t.classList.remove('active');
    });
    Array.prototype.forEach.call(document.querySelectorAll('.tab'), function (t) {
        t.classList.remove('active');
    });
    document.getElementById(tabName + '-tab').classList.add('active');
    var selector = '[data-tab="' + tabName + '"]';
    var el = document.querySelector(selector);
    if (el) el.classList.add('active');
    // Handle tab-specific refreshes
    if (tabName === 'metrics') {
        // If switching to metrics tab and we have metrics, display them
        if (window.lastMetrics) {
            displayMetrics(window.lastMetrics);
        } else {
            displayMetrics(null); // Show "no metrics" message
        }
    } else if (tabName === 'mapping' && window.lastResult) {
        // If switching to mapping tab, ensure correct data is displayed - support both formats
        var hmdMerged = window.lastResult.data.HMD_Merged_Schema || (window.lastResult.data.Merged_Schema && window.lastResult.data.Merged_Schema.HMD_Merged_Schema);
        var vmdMerged = window.lastResult.data.VMD_Merged_Schema || (window.lastResult.data.Merged_Schema && window.lastResult.data.Merged_Schema.VMD_Merged_Schema);
        if (hmdMerged || vmdMerged) {
            // This is a merge operation - use match results for Schema Mapping and show merged table
            var mergedSchemaSection = document.getElementById('mergedSchemaSection');
            var mainMergedContainer = document.getElementById('mainMergedSchemaDisplay');

            // FIRST call displayEnhancedMapping (which clears the merged table)
            if (window.lastResult.match_result) {
                console.log('🔄 Tab switch to mapping - using match results for merge operation');
                displayEnhancedMapping(window.lastResult.match_result);
            } else {
                displayEnhancedMapping(window.lastResult.data);
            }

            // THEN ensure merged schema table is populated AFTER displayEnhancedMapping cleared it
            if (mergedSchemaSection && mainMergedContainer) {
                console.log('🔄 Tab switch - ensuring merged schema section is visible');
                mergedSchemaSection.style.display = 'block';
                var mergedSchemaTable = createMergedSchemaTable(window.lastResult.data);
                if (Object.keys(mergedSchemaTable).length > 0) {
                    console.log('🔄 Tab switch - recreating merged schema table');
                    mainMergedContainer.innerHTML = createEnhancedTable(mergedSchemaTable, 'main-merged', null);
                    // Apply coloring to merged table - improved timing
                    setTimeout(function () {
                        var checkbox = document.getElementById('sourceDataToggle');
                        var showData = checkbox ? checkbox.checked : true;
                        updateTableDataDisplay('mainMergedSchemaDisplay', showData);
                        // Apply dashed border styling after table is rendered - nested timeout for reliability
                        setTimeout(function () {
                            addVerticalDashedLines('mainMergedSchemaDisplay');
                        }, 50);
                    }, 200);
                } else {
                    console.log('[WARNING] Tab switch - merged schema table is empty');
                }
            }
        } else {
            // This is a match operation - use main data and hide merged schema section
            displayEnhancedMapping(window.lastResult.data);
            var mergedSchemaSection = document.getElementById('mergedSchemaSection');
            if (mergedSchemaSection) {
                mergedSchemaSection.style.display = 'none';
            }
        }
    }
}
// Generate UUID for session tracking
function generateUUID() {
    return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function (c) {
        var r = Math.random() * 16 | 0;
        var v = c == 'x' ? r : (r & 0x3 | 0x8);
        return v.toString(16);
    });
}
// === API Keys Management Functions ===
function toggleApiKeysSection() {
    const section = document.getElementById('apiKeysSection');
    const button = document.getElementById('toggleApiKeys');
    if (section.style.display === 'none') {
        section.style.display = 'block';
        button.textContent = 'Hide';
        loadSavedApiKeys(); // Load any previously saved keys
    } else {
        section.style.display = 'none';
        button.textContent = 'Show/Hide';
    }
}
function saveApiKeys() {
    const groqKey = document.getElementById('groqApiKey').value.trim();
    const geminiKey = document.getElementById('geminiApiKey').value.trim();
    const anthropicKey = document.getElementById('anthropicApiKey').value.trim();
    // Save to localStorage
    if (groqKey) localStorage.setItem('groq_api_key', groqKey);
    if (geminiKey) localStorage.setItem('gemini_api_key', geminiKey);
    // if (anthropicKey) localStorage.setItem('anthropic_api_key', anthropicKey);
    showApiKeyStatus('✅ API keys saved successfully!', 'success');
}
function clearApiKeys() {
    // Clear from localStorage
    localStorage.removeItem('groq_api_key');
    localStorage.removeItem('gemini_api_key');
    // localStorage.removeItem('anthropic_api_key');
    // Clear input fields
    document.getElementById('groqApiKey').value = '';
    document.getElementById('geminiApiKey').value = '';
    document.getElementById('anthropicApiKey').value = '';
    showApiKeyStatus('🗑️ API keys cleared!', 'info');
}
function loadSavedApiKeys() {
    // Load from localStorage
    const groqKey = localStorage.getItem('groq_api_key');
    const geminiKey = localStorage.getItem('gemini_api_key');
    // const anthropicKey = localStorage.getItem('anthropic_api_key');
    if (groqKey) {
        document.getElementById('groqApiKey').value = groqKey;
    }
    if (geminiKey) {
        document.getElementById('geminiApiKey').value = geminiKey;
    }
    // if (anthropicKey) {
    //     document.getElementById('anthropicApiKey').value = anthropicKey;
    // }
}
async function testApiKeys() {
    showApiKeyStatus('🔄 Testing API keys...', 'info');
    const apiKeys = {};
    const groqKey = document.getElementById('groqApiKey').value.trim();
    const geminiKey = document.getElementById('geminiApiKey').value.trim();
    const anthropicKey = document.getElementById('anthropicApiKey').value.trim();
    if (groqKey) apiKeys.groq = groqKey;
    if (geminiKey) apiKeys.gemini = geminiKey;
    if (anthropicKey) apiKeys.anthropic = anthropicKey;
    try {
        const response = await fetch(API_BASE_URL + '/test-api-keys', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ apiKeys })
        });
        const result = await response.json();
        if (result.success) {
            let message = '✅ API Key Test Results:\\n';
            if (result.results.groq) message += `• Groq: ${result.results.groq}\\n`;
            if (result.results.gemini) message += `• Gemini: ${result.results.gemini}\\n`;
            if (result.results.anthropic) message += `• Anthropic: ${result.results.anthropic}\\n`;
            showApiKeyStatus(message, 'success');
        } else {
            showApiKeyStatus(`❌ Test failed: ${result.error}`, 'error');
        }
    } catch (error) {
        showApiKeyStatus(`❌ Test error: ${error.message}`, 'error');
    }
}
function showApiKeyStatus(message, type) {
    const statusDiv = document.getElementById('apiKeyStatus');
    statusDiv.style.display = 'block';
    statusDiv.textContent = message;
    // Set colors based on type
    if (type === 'success') {
        statusDiv.style.backgroundColor = '#d4edda';
        statusDiv.style.color = '#155724';
        statusDiv.style.border = '1px solid #c3e6cb';
    } else if (type === 'error') {
        statusDiv.style.backgroundColor = '#f8d7da';
        statusDiv.style.color = '#721c24';
        statusDiv.style.border = '1px solid #f5c6cb';
    } else { // info
        statusDiv.style.backgroundColor = '#d1ecf1';
        statusDiv.style.color = '#0c5460';
        statusDiv.style.border = '1px solid #bee5eb';
    }
    // Auto-hide after 5 seconds
    setTimeout(() => {
        statusDiv.style.display = 'none';
    }, 5000);
}
function getApiKeysForRequest() {
    // Get API keys from localStorage for sending with requests
    const keys = {};
    const groqKey = localStorage.getItem('groq_api_key');
    const geminiKey = localStorage.getItem('gemini_api_key');
    // const anthropicKey = localStorage.getItem('anthropic_api_key');
    if (groqKey) keys.groq = groqKey;
    if (geminiKey) keys.gemini = geminiKey;
    // if (anthropicKey) keys.anthropic = anthropicKey;
    return keys;
}

// Fetch and display pipeline performance metrics
async function fetchPipelineMetrics() {
    console.log('[METRICS] fetchPipelineMetrics called');
    const metricsSection = document.getElementById('metricsSection');
    const metricsLoading = document.getElementById('metricsLoading');
    const metricsContent = document.getElementById('metricsContent');
    const metricsError = document.getElementById('metricsError');
    const metricsBreakdown = document.getElementById('metricsBreakdown');

    console.log('[METRICS] Elements found:', {
        metricsSection: !!metricsSection,
        metricsLoading: !!metricsLoading,
        metricsContent: !!metricsContent,
        metricsError: !!metricsError
    });

    // Get current pipeline configuration
    const matchOperation = document.getElementById('matchOperation').value;
    const matchMethod = document.getElementById('schemaMatchingType').value;
    const matchLLM = document.getElementById('matchingLLM').value;
    const mergeContainer = document.getElementById('mergeStepContainer');
    const isMergeVisible = document.getElementById('mergeOperation') && document.getElementById('mergeOperation').value !== '';
    const mergeOperation = isMergeVisible ? document.getElementById('mergeOperation').value : null;
    const mergeMethod = isMergeVisible ? document.getElementById('mergeMethod').value : null;
    const mergeLLM = isMergeVisible ? document.getElementById('mergeLLM').value : null;

    // Only fetch if we have at least match configuration
    console.log('[METRICS] Pipeline config:', { matchOperation, matchMethod, matchLLM });
    if (!matchOperation || !matchMethod || !matchLLM) {
        console.log('[METRICS] Missing configuration, hiding metrics');
        if (metricsSection) metricsSection.style.display = 'none';
        return;
    }

    // Show loading state
    metricsSection.style.display = 'block';
    metricsLoading.style.display = 'block';
    metricsContent.style.display = 'none';
    metricsError.style.display = 'none';

    // Normalize method values to match what API expects
    const normalizeMethod = (method) => {
        if (method === 'json_default') return 'JSON (Default)';
        if (method === 'json_cot') return 'JSON';
        if (method === 'kg_default') return 'Knowledge Graph';
        if (method === 'table_partition_horizontal') return 'Table partition';
        // if (method === 'table_partition_vertical') return 'Table partition (Vertical)';
        return method;
    };

    // Normalize operator values
    const normalizeOperator = (operator) => {
        if (operator === 'operator') return 'Operator';
        if (operator === 'baseline') return 'Baseline';
        if (operator === 'instance_merge') return 'Instance Merge';
        if (operator === 'merge') return 'Schema Merge';
        return operator;
    };

    try {
        const requestBody = {
            matchOperator: normalizeOperator(matchOperation),
            matchMethod: normalizeMethod(matchMethod),
            matchLLM: matchLLM,
            mergeOperator: mergeOperation ? normalizeOperator(mergeOperation) : null,
            mergeMethod: mergeMethod ? normalizeMethod(mergeMethod) : null,
            mergeLLM: mergeLLM
        };

        console.log('[METRICS] Request body:', requestBody);

        const response = await fetch('/HemolixFusion/pipeline-metrics', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(requestBody)
        });

        console.log('[METRICS] Response status:', response.status);
        const data = await response.json();
        console.log('[METRICS] Response data:', data);

        if (data.success && data.metrics && !data.metrics.error) {
            const metrics = data.metrics;

            // Hide loading and error, show content
            metricsLoading.style.display = 'none';
            metricsError.style.display = 'none';
            metricsContent.style.display = 'block';

            // Update metrics
            document.getElementById('metricCost').textContent = `$${metrics.avg_cost.toFixed(6)}`;
            document.getElementById('metricTime').textContent = `${metrics.avg_total_time.toFixed(2)}s`;
            document.getElementById('metricAccuracy').textContent = `${(metrics.avg_accuracy * 100).toFixed(1)}%`;

            // Show breakdown if merge is included (only if breakdown element exists)
            if (metricsBreakdown) {
                if (isMergeVisible && metrics.avg_merge_time > 0) {
                    metricsBreakdown.style.display = 'block';
                    document.getElementById('metricMatchTime').textContent = `${metrics.avg_match_time.toFixed(2)}s`;
                    document.getElementById('metricMergeTime').textContent = `${metrics.avg_merge_time.toFixed(2)}s`;
                    document.getElementById('metricInputTokens').textContent = Math.round(metrics.avg_input_tokens);
                    document.getElementById('metricOutputTokens').textContent = Math.round(metrics.avg_output_tokens);
                } else {
                    metricsBreakdown.style.display = 'none';
                }
            }
        } else {
            // Show error state
            metricsLoading.style.display = 'none';
            metricsError.style.display = 'block';
            document.getElementById('metricsErrorText').textContent =
                data.metrics?.error || 'No performance data available for this configuration';
        }
    } catch (error) {
        console.error('[METRICS] Error fetching metrics:', error);
        console.error('[METRICS] Error stack:', error.stack);
        if (metricsLoading) metricsLoading.style.display = 'none';
        if (metricsContent) metricsContent.style.display = 'none';
        if (metricsError) {
            metricsError.style.display = 'block';
            document.getElementById('metricsErrorText').textContent =
                'Failed to load performance metrics';
        }
    }
}

// Profile view management
let sourceProfileData = null;
let targetProfileData = null;

// Switch between Preview and Profile views
function switchView(schemaType, viewType) {
    // Update button states
    const buttons = document.querySelectorAll(`#${schemaType}Parsed .view-toggle-btn`);
    buttons.forEach(btn => {
        if (btn.textContent.toLowerCase() === viewType) {
            btn.classList.add('active');
        } else {
            btn.classList.remove('active');
        }
    });

    // Show/hide appropriate sections
    const previewSection = document.getElementById(`${schemaType}PreviewSection`);
    const profileSection = document.getElementById(`${schemaType}ProfileSection`);

    if (viewType === 'preview') {
        previewSection.style.display = 'block';
        profileSection.style.display = 'none';
    } else if (viewType === 'profile') {
        previewSection.style.display = 'none';
        profileSection.style.display = 'block';

        // Render profile if not already rendered
        const profileData = schemaType === 'source' ? sourceProfileData : targetProfileData;
        if (profileData) {
            renderProfile(schemaType, profileData);
        }
    }
}

// Render profile data
function renderProfile(schemaType, profileData) {
    const container = document.getElementById(`${schemaType}Profile`);

    if (!profileData || !profileData.summary) {
        container.innerHTML = '<p style="text-align: center; color: #999;">No profile data available</p>';
        return;
    }

    let html = '';

    // Summary section
    html += '<div class="profile-summary">';
    html += '<h5>📊 Document Summary</h5>';

    for (const [label, value] of Object.entries(profileData.summary)) {
        html += `
            <div class="profile-item">
                <span class="profile-label">${label}</span>
                <span class="profile-value">${value}</span>
            </div>
        `;
    }

    html += '</div>';

    // Tables breakdown
    if (profileData.tables && profileData.tables.length > 0) {
        html += '<div class="profile-tables">';
        html += '<h5>📋 Table Breakdown</h5>';
        html += '<table class="profile-table">';
        html += '<thead><tr>';
        html += '<th>Table Name</th>';
        html += '<th>HMDs</th>';
        html += '<th>VMDs</th>';
        html += '<th>Data Rows</th>';
        html += '</tr></thead>';
        html += '<tbody>';

        for (const table of profileData.tables) {
            html += '<tr>';
            html += `<td>${table.table_name}</td>`;
            html += `<td>${table.hmds}</td>`;
            html += `<td>${table.vmds}</td>`;
            html += `<td>${table.data_rows}</td>`;
            html += '</tr>';
        }

        html += '</tbody></table>';
        html += '</div>';
    }

    container.innerHTML = html;
}

// Count data rows from schema
function countDataRowsFromSchema(schemaData) {
    if (!schemaData || typeof schemaData !== 'object') return 0;

    let dataRowCount = 0;
    for (const [key, value] of Object.entries(schemaData)) {
        if (key.endsWith('.Data') && Array.isArray(value)) {
            dataRowCount += value.length;
        }
    }
    return dataRowCount;
}

// Calculate partition stats locally
function calculatePartitionStatsLocal(dataRows1, dataRows2) {
    if (dataRows1 <= 0 || dataRows2 <= 0) {
        return null;
    }

    // partitions = floor(sqrt((dataRows1 * dataRows2) / (dataRows1 + dataRows2)))
    const numerator = dataRows1 * dataRows2;
    const denominator = dataRows1 + dataRows2;
    const partitions = Math.max(1, Math.floor(Math.sqrt(numerator / denominator)));

    // partition_size_table1 = ceil(dataRows1 / partitions)
    const table1_partition_size = Math.ceil(dataRows1 / partitions);
    const table1_rest = dataRows1 % table1_partition_size;

    // partition_size_table2 = ceil(dataRows2 / partitions)
    const table2_partition_size = Math.ceil(dataRows2 / partitions);
    const table2_rest = dataRows2 % table2_partition_size;

    return {
        partitions: partitions,
        table1_data_rows: dataRows1,
        table1_partition_size: table1_partition_size,
        table1_rest: table1_rest,
        table2_data_rows: dataRows2,
        table2_partition_size: table2_partition_size,
        table2_rest: table2_rest
    };
}

// Update partition stats preview when merge method changes
function updatePartitionStatsPreview() {
    const mergeMethod = document.getElementById('mergeMethod').value;

    // Check if table partition method is selected
    if (mergeMethod === 'table_partition_horizontal' || mergeMethod === 'table_partition_vertical') {
        // Check if both schemas are loaded
        if (sourceData && targetData) {
            // Count data rows from both schemas
            const sourceDataRows = countDataRowsFromSchema(sourceData);
            const targetDataRows = countDataRowsFromSchema(targetData);

            // Calculate partition stats
            const stats = calculatePartitionStatsLocal(sourceDataRows, targetDataRows);

            if (stats) {
                displayPartitionStats(stats);
                console.log('[DEBUG] Partition stats preview calculated:', stats);

                // Call backend to create partition file
                createPartitionFile(mergeMethod);
            } else {
                hidePartitionStats();
            }
        } else {
            hidePartitionStats();
        }
    } else {
        // Hide partition stats for other methods
        hidePartitionStats();
    }
}

// Create partition analysis file on the backend
async function createPartitionFile(mergeMethod) {
    if (!sourceData || !targetData) {
        console.log('[PARTITION] Cannot create partition file - missing schema data');
        return;
    }

    try {
        console.log('[PARTITION] Creating partition file for method:', mergeMethod);

        const response = await fetch(API_BASE_URL + '/create-partitions', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                sourceSchema: JSON.stringify(sourceData),
                targetSchema: JSON.stringify(targetData),
                mergeMethod: mergeMethod
            })
        });

        const result = await response.json();

        if (result.success) {
            console.log('[PARTITION] Partition file created successfully:', result.partition_file);
            console.log('[PARTITION] Source partitions:', result.source_partitions_count);
            console.log('[PARTITION] Target partitions:', result.target_partitions_count);

            // SAVE partition data for reuse in Phase 4 (skip Phase 3 recreation)
            window.savedPartitionInfo = result.partitions;
            window.savedPartitionStats = result.partition_stats;
            console.log('[PARTITION] Saved partition info for Phase 4:', window.savedPartitionInfo);
        } else {
            console.error('[PARTITION] Failed to create partition file:', result.error);
        }
    } catch (error) {
        console.error('[PARTITION] Error creating partition file:', error);
    }
}


// Display partition statistics
function displayPartitionStats(stats) {
    var statsSection = document.getElementById('partitionStatsSection');
    if (!statsSection) return;

    // Show the section
    statsSection.style.display = 'block';

    // Update all stat values
    document.getElementById('partitionCount').textContent = stats.partitions || '-';
    document.getElementById('table1DataRows').textContent = stats.table1_data_rows || '-';
    document.getElementById('table1PartitionSize').textContent = stats.table1_partition_size || '-';
    document.getElementById('table1Rest').textContent = stats.table1_rest || '-';
    document.getElementById('table2DataRows').textContent = stats.table2_data_rows || '-';
    document.getElementById('table2PartitionSize').textContent = stats.table2_partition_size || '-';
    document.getElementById('table2Rest').textContent = stats.table2_rest || '-';

    console.log('[DEBUG] Partition stats displayed:', stats);
}

// Hide partition statistics section
function hidePartitionStats() {
    var statsSection = document.getElementById('partitionStatsSection');
    if (statsSection) {
        statsSection.style.display = 'none';
    }
}

// Store profile data when schemas are loaded
window.storeProfileData = function (schemaType, profile) {
    if (schemaType === 'source') {
        sourceProfileData = profile;
    } else if (schemaType === 'target') {
        targetProfileData = profile;
    }
};

// Initialize resizable preview/profile containers
function initializeResizableContainers() {
    const containers = [
        'sourcePreview',
        'targetPreview',
        'sourceProfile',
        'targetProfile'
    ];

    containers.forEach(containerId => {
        const container = document.getElementById(containerId);
        if (container) {
            // Enable overflow when container is resized
            const observer = new ResizeObserver(entries => {
                for (let entry of entries) {
                    const element = entry.target;
                    // Ensure proper overflow behavior when resized
                    if (element.scrollHeight > element.clientHeight ||
                        element.scrollWidth > element.clientWidth) {
                        element.style.overflow = 'auto';
                    }
                }
            });
            observer.observe(container);
        }
    });
}

// Initialize on page load
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initializeResizableContainers);
} else {
    initializeResizableContainers();
}

// ============================================================================
// MOCK DATA TEST FUNCTION - Call testMergedTable() from browser console
// ============================================================================
window.testMergedTable = function () {
    console.log('🧪 [TEST] Starting merged table test with COMPLETE REAL data...');

    // Full real dataset from user provided partition_merge_results
    var mockResultData = {
        "HMD_Merged_Schema": [
            "Year ended December 31,.2019",
            "Year ended December 31,.2018",
            "Year ended December 31,.2017",
            "Year ended December 31,.2016",
            "Year ended December 31,.2015",
            "Year ended December 31,.2014"
        ],
        "VMD_Merged_Schema": [
            "Financial Data (in millions, except per share amounts):.Income before taxes",
            "Financial Data (in millions, except per share amounts):.Net income",
            "Financial Data (in millions, except per share amounts):.Operating expenses",
            "Financial Data (in millions, except per share amounts):.Operating income",
            "Financial Data (in millions, except per share amounts):.Operating revenues",
            "Financial Data (in millions, except per share amounts):.Other expenses (income) net",
            "Financial Data (in millions, except per share amounts):.Provision (benefit) for income taxes",
            "Financial Data (in millions, except per share amounts):.Provision for income taxes",
            "Financial Data (in millions, except per share amounts):.Cash dividends per common share",
            "Financial Data (in millions, except per share amounts):.Long-term obligations at period-end",
            "Financial Data (in millions, except per share amounts):.Net income per share, basic",
            "Financial Data (in millions, except per share amounts):.Net income per share, diluted",
            "Financial Data (in millions, except per share amounts):.Stockholders’ equity at period-end",
            "Financial Data (in millions, except per share amounts):.Total assets at period-end",
            "Operating Data:.Revenue passengers carried",
            "Operating Data:.Revenue passengers carried (000s)",
            "Operating Data:.Available seat miles (ASMs) (in millions) (b)",
            "Operating Data:.Average aircraft stage length (miles)",
            "Operating Data:.Enplaned passengers"
        ],
        "Merged_Data": {
            "Financial Data (in millions, except per share amounts):.Income before taxes": {
                "source": ["2,957", "3,164", "3,265", "3,450", "3,479", ""],
                "target": ["", "3,164", "3,265", "3,450", "3,479", "1,816"]
            },
            "Financial Data (in millions, except per share amounts):.Net income": {
                "source": ["$2,300", "$2,465", "$3,357", "$2,183", "$2,181", ""],
                "target": ["", "$2,465", "$3,357", "$2,183", "$2,181", "$1,136"]
            },
            "Financial Data (in millions, except per share amounts):.Operating expenses": {
                "source": ["19,471", "18,759", "17,739", "16,767", "15,821", ""],
                "target": ["", "18,759", "17,739", "16,767", "15,821", "16,437"]
            },
            "Financial Data (in millions, except per share amounts):.Operating income": {
                "source": ["2,957", "3,206", "3,407", "3,522", "3,999", ""],
                "target": ["", "3,206", "3,407", "3,522", "3,999", "2,168"]
            },
            "Financial Data (in millions, except per share amounts):.Operating revenues": {
                "source": ["$22,428", "$21,965", "$21,146", "$20,289", "$19,820", ""],
                "target": ["", "$21,965", "$21,146", "$20,289", "$19,820", "$18,605"]
            },
            "Financial Data (in millions, except per share amounts):.Other expenses (income) net": {
                "source": ["—", "42", "142", "72", "520", ""],
                "target": ["", "42", "142", "72", "520", "352"]
            },
            "Financial Data (in millions, except per share amounts):.Provision (benefit) for income taxes": {
                "source": ["657", "699", "(92)", "1,267", "1,298", ""],
                "target": ["", "", "", "", "", ""]
            },
            "Financial Data (in millions, except per share amounts):.Provision for income taxes": {
                "source": ["", "", "", "", "", ""],
                "target": ["", "699", "(92)", "1,267", "1,298", "680"]
            },
            "Financial Data (in millions, except per share amounts):.Cash dividends per common share": {
                "source": ["$0.700", "$0.605", "$0.475", "$0.375", "$0.285", ""],
                "target": ["", "$0.6050", "$0.4750", "$0.3750", "$0.2850", "$0.2200"]
            },
            "Financial Data (in millions, except per share amounts):.Long-term obligations at period-end": {
                "source": ["$1,846", "$2,771", "$3,320", "$2,821", "$2,541", ""],
                "target": ["", "$2,771", "$3,320", "$2,821", "$2,541", "$2,434"]
            },
            "Financial Data (in millions, except per share amounts):.Net income per share, basic": {
                "source": ["$4.28", "$4.30", "$5.58", "$3.48", "$3.30", ""],
                "target": ["", "$4.30", "$5.58", "$3.48", "$3.30", "$1.65"]
            },
            "Financial Data (in millions, except per share amounts):.Net income per share, diluted": {
                "source": ["$4.27", "$4.29", "$5.57", "$3.45", "$3.27", ""],
                "target": ["", "$4.29", "$5.57", "$3.45", "$3.27", "$1.64"]
            },
            "Financial Data (in millions, except per share amounts):.Stockholders’ equity at period-end": {
                "source": ["$9,832", "$9,853", "$9,641", "$7,784", "$7,358", ""],
                "target": ["", "$9,853", "$9,641", "$7,784", "$7,358", "$6,775"]
            },
            "Financial Data (in millions, except per share amounts):.Total assets at period-end": {
                "source": ["$25,895", "$26,243", "$25,110", "$23,286", "$21,312", ""],
                "target": ["", "$26,243", "$25,110", "$23,286", "$21,312", "$19,723"]
            },
            "Operating Data:.Revenue passengers carried": {
                "source": ["", "", "", "", "", ""],
                "target": ["", "134,890,243", "130,256,190", "124,719,765", "118,171,211", "110,496,912"]
            },
            "Operating Data:.Revenue passengers carried (000s)": {
                "source": ["134,056", "134,890", "130,256", "124,720", "118,171", ""],
                "target": ["", "", "", "", "", ""]
            },
            "Operating Data:.Available seat miles (ASMs) (in millions) (b)": {
                "source": ["131,345", "133,322", "129,041", "124,798", "117,500", ""],
                "target": ["", "", "", "", "", ""]
            },
            "Operating Data:.Average aircraft stage length (miles)": {
                "source": ["980", "988", "991", "1,001", "994", ""],
                "target": ["", "757", "754", "760", "750", "721"]
            },
            "Operating Data:.Enplaned passengers": {
                "source": ["", "", "", "", "", ""],
                "target": ["", "163,605,833", "157,677,218", "151,740,357", "144,574,882", "135,767,188"]
            }
        }
    };

    console.log('🧪 [TEST] Mock data structure populated with:', Object.keys(mockResultData.Merged_Data).length, 'keys');

    // Show the merged schema section AND ALL parent containers
    var resultsContainer = document.getElementById('resultsContainer');
    var mappingTab = document.getElementById('mapping-tab');
    var tableMappingView = document.getElementById('tableMappingView');
    var mergedSchemaSection = document.getElementById('mergedSchemaSection');
    var mainMergedContainer = document.getElementById('mainMergedSchemaDisplay');

    // Make all parent containers visible
    if (resultsContainer) {
        resultsContainer.style.display = 'block';
        console.log('🧪 [TEST] resultsContainer made visible');
    }
    if (mappingTab) {
        mappingTab.classList.add('active');
        mappingTab.style.display = 'block';
        console.log('🧪 [TEST] mapping-tab made visible');
    }
    if (tableMappingView) {
        tableMappingView.style.display = 'block';
        console.log('🧪 [TEST] tableMappingView made visible');
    }

    if (mergedSchemaSection) {
        mergedSchemaSection.style.display = 'block';
        console.log('🧪 [TEST] Merged schema section made visible');
        // Scroll to it
        setTimeout(function () {
            mergedSchemaSection.scrollIntoView({ behavior: 'smooth', block: 'start' });
        }, 200);
    } else {
        console.error('🧪 [TEST] ERROR: mergedSchemaSection not found!');
        return;
    }

    if (mainMergedContainer) {
        mainMergedContainer.innerHTML = '';
        console.log('🧪 [TEST] Cleared main merged container');
    } else {
        console.error('🧪 [TEST] ERROR: mainMergedSchemaDisplay not found!');
        return;
    }

    // Create the merged schema table
    console.log('🧪 [TEST] Calling createMergedSchemaTable...');
    var mergedSchemaTable = createMergedSchemaTable(mockResultData);
    console.log('🧪 [TEST] createMergedSchemaTable returned:', Object.keys(mergedSchemaTable));

    if (Object.keys(mergedSchemaTable).length > 0) {
        console.log('🧪 [TEST] Calling createEnhancedTable...');
        var mergedHTML = createEnhancedTable(mergedSchemaTable, 'main-merged', null);
        console.log('🧪 [TEST] HTML generated, length:', mergedHTML.length);

        mainMergedContainer.innerHTML = mergedHTML;
        console.log('🧪 [TEST] HTML injected into container');

        // Apply styling
        setTimeout(function () {
            updateTableDataDisplay('mainMergedSchemaDisplay', true);
            addVerticalDashedLines('mainMergedSchemaDisplay');
            console.log('🧪 [TEST] Styling applied');
        }, 100);
    } else {
        console.error('🧪 [TEST] ERROR: createMergedSchemaTable returned empty!');
    }

    console.log('🧪 [TEST] Test complete - check the Schema Mapping tab');

    // Switch to Schema Mapping tab
    var schemaTab = document.querySelector('.tab[data-tab="schemaMapping"]');
    if (schemaTab) {
        schemaTab.click();
        console.log('🧪 [TEST] Switched to Schema Mapping tab');
    }
};

console.log('✅ testMergedTable() function available - run it from browser console to test merged table rendering');

// ==========================================
// Automated PDF Extraction
// ==========================================

// Handle Custom Model Input
document.addEventListener('DOMContentLoaded', function () {
    var modelSelect = document.getElementById('pdfModelSelect');
    var customInput = document.getElementById('pdfModelCustom');

    if (modelSelect && customInput) {
        modelSelect.addEventListener('change', function () {
            if (this.value === 'custom') {
                customInput.style.display = 'block';
                customInput.focus();
            } else {
                customInput.style.display = 'none';
            }
        });
    }
});

function togglePdfExtraction() {
    var section = document.getElementById('pdfExtractionSection');
    var isVisible = section.style.display !== 'none';

    if (isVisible) {
        // Hiding PDF Extraction -> Restore Normal View
        section.style.display = 'none';

        // Restore other sections
        var sectionsToShow = document.querySelectorAll('.upload-section, .quick-load-section, .data-preview-section, .pipeline-config');
        sectionsToShow.forEach(function (el) {
            if (el.id !== 'pdfExtractionSection') {
                el.style.display = ''; // Restore default display
            }
        });

        // Update button appearance
        var btnText = document.getElementById('pdfExtractionText');
        var btnIcon = document.getElementById('pdfExtractionIcon');
        if (btnText) btnText.textContent = "Automated PDF Extraction";
        if (btnIcon) btnIcon.textContent = "📑";

    } else {
        // Showing PDF Extraction -> Isolate View
        section.style.display = 'block';

        // Hide other sections
        var sectionsToHide = document.querySelectorAll('.upload-section, .quick-load-section, .data-preview-section, .pipeline-config');
        sectionsToHide.forEach(function (el) {
            if (el.id !== 'pdfExtractionSection') {
                el.style.display = 'none';
            }
        });

        // Update button appearance
        var btnText = document.getElementById('pdfExtractionText');
        var btnIcon = document.getElementById('pdfExtractionIcon');
        if (btnText) btnText.textContent = "Back to Pipeline Configuration";
        if (btnIcon) btnIcon.textContent = "↩️";

        // Scroll to section
        section.scrollIntoView({ behavior: 'smooth' });

        // Check if models are loaded (retry fetch if stuck)
        var pdfSelect = document.getElementById('pdfModelSelect');
        if (pdfSelect && (pdfSelect.options.length <= 1 && pdfSelect.value === "")) {
            console.log('🔄 Models not loaded in PDF section, retrying fetch...');
            fetchModels();
        }
    }
}

function addPdfInput() {
    var container = document.getElementById('pdfInputsContainer');
    var currentRows = container.querySelectorAll('.pdf-input-row').length;

    if (currentRows >= 10) {
        alert('Maximum of 10 file pairs allowed.');
        return;
    }

    var div = document.createElement('div');
    div.className = 'pdf-input-row';
    div.style.marginBottom = '10px';
    div.style.display = 'flex';
    div.style.gap = '10px';
    div.style.alignItems = 'center';
    div.style.background = '#f5f5f5';
    div.style.padding = '10px';
    div.style.borderRadius = '8px';

    div.innerHTML = `
        <div style="flex: 1;">
            <label style="font-size: 12px; font-weight: bold; display: block; margin-bottom: 4px;">PDF File</label>
            <input type="file" accept=".pdf" class="pdf-file-input" style="width: 100%; padding: 5px; border: 1px solid #ccc; border-radius: 4px;">
        </div>
        <div style="flex: 1;">
            <label style="font-size: 12px; font-weight: bold; display: block; margin-bottom: 4px;">Target Schema (JSON)</label>
            <input type="file" accept=".json" class="schema-file-input" style="width: 100%; padding: 5px; border: 1px solid #ccc; border-radius: 4px;">
        </div>
        <button onclick="removePdfInput(this)" style="background: #ffcdd2; color: #c62828; border: none; padding: 8px 12px; border-radius: 6px; cursor: pointer; font-weight: bold; height: fit-content; align-self: center;">✕</button>
    `;

    container.appendChild(div);
    checkAddButton();
}

function removePdfInput(btn) {
    btn.parentElement.remove();
    checkAddButton();
}

function checkAddButton() {
    var container = document.getElementById('pdfInputsContainer');
    var currentRows = container.querySelectorAll('.pdf-input-row').length;
    var addBtn = document.getElementById('addPdfBtn');

    if (currentRows >= 10) {
        addBtn.disabled = true;
        addBtn.style.opacity = '0.5';
        addBtn.style.cursor = 'not-allowed';
    } else {
        addBtn.disabled = false;
        addBtn.style.opacity = '1';
        addBtn.style.cursor = 'pointer';
    }
}

async function extractPdfData() {
    var container = document.getElementById('pdfInputsContainer');
    var rows = container.querySelectorAll('.pdf-input-row');
    var pdfFiles = [];
    var schemaFiles = [];

    rows.forEach(function (row) {
        var pdfInput = row.querySelector('.pdf-file-input');
        var schemaInput = row.querySelector('.schema-file-input');

        if (pdfInput.files.length > 0 && schemaInput.files.length > 0) {
            pdfFiles.push(pdfInput.files[0]);
            schemaFiles.push(schemaInput.files[0]);
        }
    });

    const checkboxes = document.querySelectorAll('.preload-checkbox:checked');
    const preloadFolders = Array.from(checkboxes).map(cb => cb.value);

    if (pdfFiles.length === 0 && preloadFolders.length === 0) {
        alert('Please provide at least one manual file pair or select one local folder.');
        return;
    }

    var resultsDiv = document.getElementById('pdfExtractionResults');
    const totalTasks = (pdfFiles.length > 0 ? 1 : 0) + preloadFolders.length;
    let completedTasks = 0;

    resultsDiv.innerHTML = '<div style="text-align: center; padding: 20px;"><div class="spinner"></div><p id="extractionProgress">Preparing extraction batch...</p></div>';
    const progressText = document.getElementById('extractionProgress');

    // Get Shared Model/Settings
    const modelSelect = document.getElementById('pdfModelSelect');
    const customInput = document.getElementById('pdfModelCustom');
    let llmModel = 'Qwen2.5:14B';
    if (modelSelect) {
        llmModel = modelSelect.value;
        if (llmModel === 'custom' && customInput) {
            llmModel = customInput.value || 'Qwen2.5:14B';
        }
    }

    const tuplesInput = document.getElementById('tuplesPerPartition');
    const tuplesPerPartition = tuplesInput ? parseInt(tuplesInput.value) || 5 : 5;

    // 1. Process Manual Files (as a batch)
    if (pdfFiles.length > 0) {
        const manualProgress = totalTasks > 1 ? `Extracting ${pdfFiles.length} manual pair(s)... (${completedTasks + 1}/${totalTasks})` : `Extracting ${pdfFiles.length} manual pair(s)...`;
        renderPdfExtractionResults({ results: window.pdfExtractionResults || [] }, manualProgress);

        var formData = new FormData();
        pdfFiles.forEach(f => formData.append('files', f));
        schemaFiles.forEach(f => formData.append('schema_files', f));
        formData.append('llm_model', llmModel);
        formData.append('tuples_per_partition', tuplesPerPartition);

        try {
            const response = await fetch('/HemolixFusion/extract_pdf', { method: 'POST', body: formData });
            const data = await response.json();
            if (data.results) {
                if (!window.pdfExtractionResults) window.pdfExtractionResults = [];
                window.pdfExtractionResults = window.pdfExtractionResults.concat(data.results);
            }
        } catch (err) {
            console.error('Manual extraction error:', err);
            showError('Manual extraction failed: ' + err.message);
        }
        completedTasks++;
    }

    // 2. Process Preloads (sequentially)
    for (let i = 0; i < preloadFolders.length; i++) {
        const folderName = preloadFolders[i];
        const preloadProgress = `Processing local folder: ${folderName} (${completedTasks + 1}/${totalTasks})`;
        renderPdfExtractionResults({ results: window.pdfExtractionResults || [] }, preloadProgress);

        try {
            const response = await fetch(API_BASE_URL + '/run-pdf-preload', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    folder_name: folderName,
                    llm_model: llmModel,
                    tuples_per_partition: tuplesPerPartition
                })
            });

            const data = await response.json();
            if (data.results) {
                if (!window.pdfExtractionResults) window.pdfExtractionResults = [];
                window.pdfExtractionResults = window.pdfExtractionResults.concat(data.results);
            } else if (data.error) {
                showError(`Error with '${folderName}': ` + data.error);
            }
        } catch (err) {
            console.error(`Preload error (${folderName}):`, err);
            showError(`Preload failed (${folderName}): ` + err.message);
        }
        completedTasks++;
    }

    // Final UI refresh (Clear progress bar)
    renderPdfExtractionResults({ results: window.pdfExtractionResults || [] });

    // Final UI refresh
    if (!window.pdfExtractionResults || window.pdfExtractionResults.length === 0) {
        resultsDiv.innerHTML = '<div style="color: #c62828;">No results extracted. Check consoles for details.</div>';
    }
}

// ==========================================
// Strict Mode Separation Logic
// ==========================================

function applyModeSeparation() {
    const urlParams = new URLSearchParams(window.location.search);
    const mode = urlParams.get('mode');

    console.log('[Strict Mode] Applying separation for mode:', mode);

    // Elements
    const pdfSection = document.getElementById('pdfExtractionSection');
    const pdfButton = document.getElementById('togglePdfExtraction'); // The toggle button container/button

    // Selectors for Fusion elements
    const uploadSection = document.querySelector('.upload-section');
    const quickLoadSection = document.querySelector('.quick-load-section');
    const pipelineConfig = document.querySelectorAll('.pipeline-config'); // Returns NodeList
    const processBtn = document.getElementById('processBtn');
    const dataPreview = document.querySelector('.data-preview-section');

    if (mode === 'pdf') {
        console.log('[Strict Mode] Activating PDF Extraction View');

        // 1. Show PDF Section
        if (pdfSection) {
            pdfSection.style.display = 'block';
            // Trigger model fetch if needed
            const pdfSelect = document.getElementById('pdfModelSelect');
            if (pdfSelect && (pdfSelect.options.length <= 1 && pdfSelect.value === "")) {
                if (typeof fetchModels === 'function') fetchModels();
            }
        } else {
            console.error('[Strict Mode] PDF Section not found!');
        }

        // 2. Hide common Fusion elements
        if (uploadSection) uploadSection.style.display = 'none';
        if (quickLoadSection) quickLoadSection.style.display = 'none';
        if (dataPreview) dataPreview.style.display = 'none';
        if (processBtn) processBtn.style.display = 'none';

        // 3. Hide all pipeline configs EXCEPT the PDF one
        pipelineConfig.forEach(el => {
            if (el.id !== 'pdfExtractionSection') {
                el.style.display = 'none';
            }
        });

        // 4. Hide the toggle button (users are already here)
        if (pdfButton) {
            pdfButton.style.display = 'none';
            // Also try to hide the parent container if it's just for the button
            if (pdfButton.parentElement && pdfButton.parentElement.style.textAlign === 'center') {
                pdfButton.parentElement.style.display = 'none';
            }
        }

    } else if (mode === 'fusion') {
        console.log('[Strict Mode] Activating Manual Fusion View');

        // 1. Hide PDF Section
        if (pdfSection) pdfSection.style.display = 'none';

        // 2. Hide PDF Toggle Button (Strict separation)
        if (pdfButton) {
            pdfButton.style.display = 'none';
            if (pdfButton.parentElement && pdfButton.parentElement.style.textAlign === 'center') {
                pdfButton.parentElement.style.display = 'none';
            }
        }

        // 3. Ensure Fusion elements are visible
        if (uploadSection) uploadSection.style.display = '';
        if (quickLoadSection) quickLoadSection.style.display = '';
        if (dataPreview) dataPreview.style.display = '';
        if (processBtn) processBtn.style.display = 'none'; // Process button usually hidden until needed

        // 4. Show Fusion Pipeline Config (Hidden by default or by PDF mode)
        pipelineConfig.forEach(el => {
            if (el.id !== 'pdfExtractionSection') {
                el.style.display = ''; // Restore
            }
        });

    } else {
        // Default View (Landing or direct /tool access)
        console.log('[Strict Mode] Default View');
        // If strict separation is desired, maybe default to Fusion but hide PDF section?
        if (pdfSection) pdfSection.style.display = 'none';
        // if (pdfButton) pdfButton.style.display = 'none'; // Optional
    }
}

// Run on load
document.addEventListener('DOMContentLoaded', applyModeSeparation);
// Also run on window.onload to catch any late rendering
window.addEventListener('load', applyModeSeparation);

// ==========================================
// Fetch Models Function (Missing Implementation)
// ==========================================

// function fetchModels() {
//     console.log('[fetchModels] Fetching available models from backend...');

//     // Read from static text file instead of API
//     fetch('/HemolixFusion/static/models.txt')
//         .then(response => response.text())
//         .then(text => {
//             // Parse text file (one model per line)
//             const models = text.trim().split('\n').map(line => line.trim()).filter(line => line.length > 0);
//             console.log('[fetchModels] Loaded models from file:', models);

//             if (models.length > 0) {
//                 // Populate all model dropdowns
//                 const modelSelects = [
//                     document.getElementById('pdfModelSelect'),
//                     document.getElementById('matchingLLM'),
//                     document.getElementById('mergeLLM')
//                 ];

//                 modelSelects.forEach(select => {
//                     if (!select) return;

//                     // Get existing values and texts for deduplication (case-insensitive)
//                     const existingVals = Array.from(select.options).map(o => o.value.toLowerCase().trim());
//                     const existingTexts = Array.from(select.options).map(o => o.text.toLowerCase().trim());

//                     // Add models from file that aren't already there
//                     models.forEach(model => {
//                         const mLower = model.toLowerCase().trim();
//                         // Only add if neither the value nor the text matches existing options
//                         if (!existingVals.includes(mLower) && !existingTexts.includes(mLower)) {
//                             const option = document.createElement('option');
//                             option.value = model;
//                             option.textContent = model;
//                             select.appendChild(option);
//                         }
//                     });

//                     // Add custom option for PDF select if not there
//                     if (select.id === 'pdfModelSelect' && !existingVals.includes('custom')) {
//                         const customOption = document.createElement('option');
//                         customOption.value = 'custom';
//                         customOption.textContent = 'Custom Model...';
//                         select.appendChild(customOption);
//                     }

//                     // Remove "Loading models..." placeholder if present
//                     for (let i = 0; i < select.options.length; i++) {
//                         if (select.options[i] && select.options[i].text.toLowerCase().includes("loading")) {
//                             select.remove(i);
//                             break;
//                         }
//                     }

//                     console.log(`[fetchModels] Deduped and updated #${select.id}`);
//                 });
//             } else {
//                 console.error('[fetchModels] No models found in file');
//             }
//         })
//         .catch(error => {
//             console.error('[fetchModels] Error fetching models:', error);

//             // Fallback: Add a default option
//             const modelSelects = [
//                 document.getElementById('pdfModelSelect'),
//                 document.getElementById('matchingLLM'),
//                 document.getElementById('mergeLLM')
//             ];

//             modelSelects.forEach(select => {
//                 if (!select) return;
//                 select.innerHTML = '<option value="">Error loading models</option>';
//             });
//         });
// }

// Fusion Data Transfer Function
function fuseExtractedData() {
    if (!window.pdfExtractionResults || window.pdfExtractionResults.length < 2) {
        alert('Need at least 2 extraction results to fuse data.');
        return;
    }

    // Collect successful extractions only
    const fusionData = window.pdfExtractionResults
        .filter(result => result.success && result.extracted_data)
        .map(result => ({
            filename: result.filename,
            data: result.extracted_data
        }));

    if (fusionData.length < 2) {
        alert('Need at least 2 successful extractions to fuse data.');
        return;
    }

    // Store in sessionStorage
    sessionStorage.setItem('fusionPrefilledData', JSON.stringify(fusionData));

    // Navigate to fusion page
    window.location.href = '/HemolixFusion/tool?mode=fusion&prefilled=true';
}

// Auto-fetch models on page load
document.addEventListener('DOMContentLoaded', function () {
    // Small delay to ensure dropdowns are rendered

    // setTimeout(fetchModels, 100);

    // Fetch PDF preloads
    setTimeout(fetchPdfPreloads, 150);

    // Check for prefilled fusion data
    setTimeout(checkForPrefilledFusionData, 200);
});

async function fetchPdfPreloads() {
    console.log('[PRELOAD] Fetching available PDF preloads...');
    const listDiv = document.getElementById('pdfPreloadList');
    if (!listDiv) return;

    try {
        const response = await fetch(API_BASE_URL + '/list-pdf-preloads');
        const data = await response.json();

        if (data.preloads && data.preloads.length > 0) {
            listDiv.innerHTML = '';
            data.preloads.forEach(folder => {
                const itemLabel = document.createElement('label');
                itemLabel.className = 'preload-item';
                itemLabel.style.cssText = 'display: flex; align-items: center; gap: 8px; font-size: 13px; color: #333; cursor: pointer; padding: 4px; border-radius: 4px; transition: background 0.2s;';
                itemLabel.onmouseover = () => itemLabel.style.background = '#f1f8ff';
                itemLabel.onmouseout = () => itemLabel.style.background = 'transparent';

                itemLabel.innerHTML = `
                    <input type="checkbox" class="preload-checkbox" value="${folder}" style="cursor: pointer;">
                    <span>📁 ${folder}</span>
                `;
                listDiv.appendChild(itemLabel);
            });
            console.log(`[PRELOAD] Found ${data.preloads.length} local preloads`);
        } else {
            listDiv.innerHTML = '<div style="color: #666; font-style: italic; font-size: 12px; text-align: center; padding: 10px;">No folders found in pdf_preloads/</div>';
        }
    } catch (err) {
        console.error('[PRELOAD] Error fetching preloads:', err);
        listDiv.innerHTML = '<div style="color: #c62828; font-size: 12px; text-align: center; padding: 10px;">Error loading preloads</div>';
    }
}

function toggleAllPreloads(checked) {
    const checkboxes = document.querySelectorAll('.preload-checkbox');
    checkboxes.forEach(cb => cb.checked = checked);
}

async function runPdfPreload() {
    // Both buttons (Manual and Quick Load) now use the same unified logic
    await extractPdfData();
}

// Factor out results rendering for reuse
function renderPdfExtractionResults(data, progressMsg = null) {
    const resultsDiv = document.getElementById('pdfExtractionResults');
    resultsDiv.innerHTML = '';

    // Show Batch Progress if provided
    if (progressMsg) {
        const progressDiv = document.createElement('div');
        progressDiv.style.cssText = 'background: rgba(46, 125, 50, 0.1); border: 1px solid rgba(46, 125, 50, 0.3); padding: 12px; border-radius: 8px; margin-bottom: 20px; display: flex; align-items: center; gap: 12px;';
        progressDiv.innerHTML = `
            <div class="spinner" style="width:18px; height:18px; border-width:2px; border-top-color:#2e7d32;"></div>
            <div style="font-size: 13px; color: #2e7d32; font-weight: 500;">${progressMsg}</div>
        `;
        resultsDiv.appendChild(progressDiv);
    }

    if (!data.results || data.results.length === 0) {
        if (!progressMsg) {
            resultsDiv.innerHTML = '<div style="color: #c62828; background: #ffebee; padding: 10px; border-radius: 6px;">No results returned.</div>';
        }
        return;
    }

    if (!Array.isArray(data.results)) {
        console.error("renderPdfExtractionResults: data.results is not an array!", data.results);
        // Attempt to recover if it's a single object
        if (typeof data.results === 'object') {
            data.results = [data.results];
        } else {
            resultsDiv.innerHTML = '<div style="color: #c62828;">Error: Invalid results format received.</div>';
            return;
        }
    }

    // Show clear button container
    const clearBtn = document.getElementById('clearResultsContainer');
    if (clearBtn) clearBtn.style.display = 'block';

    // Add Header with Clear Button
    const headerDiv = document.createElement('div');
    headerDiv.style.cssText = 'display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px;';
    headerDiv.innerHTML = `
        <h3 style="margin: 0; color: white; display: flex; align-items: center; gap: 10px;">
            <span style="background: rgba(255,255,255,0.2); width: 32px; height: 32px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 16px;">📚</span>
            Extracted Collection (${data.results.length})
        </h3>
        <button onclick="clearPdfResults()" style="background: rgba(255,255,255,0.2); border: 1px solid rgba(255,255,255,0.4); color: white; padding: 5px 12px; border-radius: 4px; cursor: pointer; font-size: 12px; font-weight: 600;">Clear All Results</button>
    `;
    resultsDiv.appendChild(headerDiv);

    // Store results globally for fusion button
    window.pdfExtractionResults = data.results;

    const resultCards = [];

    data.results.forEach(function (result) {
        const resultCard = document.createElement('div');
        resultCard.style.cssText = 'background: rgba(255,255,255,0.95); border-radius: 12px; padding: 16px; backdrop-filter: blur(10px); border: 1px solid rgba(255,255,255,0.2); box-shadow: 0 2px 5px rgba(0,0,0,0.05);';

        const statusIcon = result.success ? '✅' : '❌';

        let html = `
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px; border-bottom: 1px solid #eee; padding-bottom: 8px;">
                <h4 style="margin: 0; display: flex; align-items: center; gap: 8px;">
                    ${statusIcon} <span style="color: #333;">${result.filename}</span>
                </h4>
                <span style="font-size: 12px; color: #666;">⏱️ ${result.elapsed ? result.elapsed.toFixed(2) : '0.00'}s | Model: ${result.model}</span>
            </div>
        `;

        if (result.success) {
            const schemaInfo = result.schema_info || {};
            const hmdCount = schemaInfo.hmd_count || 0;
            const vmdCount = schemaInfo.vmd_count || 0;
            const extractedCount = (result.extracted_data && result.extracted_data.Data) ? result.extracted_data.Data.length : 0;
            const fillRate = result.fill_rate ? result.fill_rate.toFixed(1) + '%' : 'N/A';

            html += `
                <div style="display: grid; grid-template-columns: 1fr 1fr 1fr 1fr; gap: 10px; margin-bottom: 15px; font-size: 13px;">
                    <div style="background: #e8f5e9; padding: 6px; border-radius: 4px; text-align: center;">
                        <div style="font-weight: bold; color: #2e7d32;">${hmdCount}</div>
                        <div style="color: #666;">HMD Cols</div>
                    </div>
                    <div style="background: #e3f2fd; padding: 6px; border-radius: 4px; text-align: center;">
                        <div style="font-weight: bold; color: #1565c0;">${vmdCount}</div>
                        <div style="color: #666;">VMD Vars</div>
                    </div>
                    <div style="background: #fff3e0; padding: 6px; border-radius: 4px; text-align: center;">
                        <div style="font-weight: bold; color: #ef6c00;">${extractedCount}</div>
                        <div style="color: #666;">Records</div>
                    </div>
                    <div style="background: #f3e5f5; padding: 6px; border-radius: 4px; text-align: center;">
                        <div style="font-weight: bold; color: #7b1fa2;">${fillRate}</div>
                        <div style="color: #666;">Fill Rate</div>
                    </div>
                </div>
            `;

            if (result.html && result.html.trim().length > 0) {
                html += `
                    <div style="margin-bottom: 15px;">
                        <h4 style="margin: 0 0 10px 0; color: #333; font-size: 14px;">📊 Extracted Data Table</h4>
                        ${result.html}
                    </div>
                `;
            }

            html += `
                <details style="background: #f8f9fa; padding: 10px; border-radius: 6px; border: 1px solid #e9ecef;">
                    <summary style="cursor: pointer; font-weight: 500; color: #495057;">View Extracted Data JSON</summary>
                    <pre style="margin-top: 10px; font-size: 11px; overflow-x: auto; white-space: pre-wrap; word-wrap: break-word; max-height: 300px; overflow-y: auto;">${JSON.stringify(result.extracted_data, null, 2)}</pre>
                </details>
            `;
        } else {
            html += `
                <div style="color: #c62828; padding: 10px; background: #ffebee; border-radius: 6px;">
                    <strong>Error:</strong> ${result.error || 'Unknown error occurred'}
                </div>
            `;
        }

        resultCard.innerHTML = html;
        resultCards.push(resultCard);
    });

    if (data.results.length >= 2) {
        const fusionButtonDiv = document.createElement('div');
        fusionButtonDiv.style.cssText = 'text-align: right; margin-bottom: 15px;';
        fusionButtonDiv.innerHTML = `
            <button onclick="fuseExtractedData()" style="background: linear-gradient(135deg, #4CAF50 0%, #45a049 100%); color: white; padding: 10px 20px; border: none; border-radius: 6px; cursor: pointer; font-size: 14px; font-weight: 500; box-shadow: 0 2px 4px rgba(0,0,0,0.1); transition: transform 0.2s;" onmouseover="this.style.transform='translateY(-2px)'" onmouseout="this.style.transform='translateY(0)'">
                🔗 Fuse Data
            </button>
        `;
        resultsDiv.appendChild(fusionButtonDiv);
    }

    if (data.results.length >= 2) {
        const gridContainer = document.createElement('div');
        gridContainer.style.cssText = 'display: grid; grid-template-columns: repeat(auto-fit, minmax(450px, 1fr)); gap: 20px;';
        resultCards.forEach(card => gridContainer.appendChild(card));
        resultsDiv.appendChild(gridContainer);
    } else {
        resultCards.forEach(card => resultsDiv.appendChild(card));
    }
}

function clearPdfResults() {
    if (confirm('Clear all extraction results?')) {
        window.pdfExtractionResults = [];
        const resultsDiv = document.getElementById('pdfExtractionResults');
        if (resultsDiv) resultsDiv.innerHTML = '';

        const clearBtn = document.getElementById('clearResultsContainer');
        if (clearBtn) clearBtn.style.display = 'none';
    }
}

async function checkForPrefilledFusionData() {
    const urlParams = new URLSearchParams(window.location.search);
    if (urlParams.get('prefilled') === 'true') {
        const dataStr = sessionStorage.getItem('fusionPrefilledData');
        if (dataStr) {
            console.log('⚡ [PREFILL] Detected fusion prefill data');
            try {
                const fusionData = JSON.parse(dataStr);
                // sessionStorage.removeItem('fusionPrefilledData'); // Keep for pool if needed, or store in window

                if (fusionData.length >= 2) {
                    window.fusionPool = fusionData; // Store globally
                    showLoading(true);

                    // Show Pool UI if 3+ tables
                    if (fusionData.length > 2) {
                        renderFusionPool();
                    }

                    // Default: Slot 0 -> Source, Slot 1 -> Target
                    await assignFromPool(0, 'source');
                    await assignFromPool(1, 'target');

                    if (fusionData.length > 2) {
                        showSuccess(`Loaded pool of ${fusionData.length} tables. Use the switcher to compare items.`);
                    } else {
                        showSuccess('Manual Schema Fusion prefilled successfully!');
                        sessionStorage.removeItem('fusionPrefilledData'); // Clean up if only 2
                    }
                }
            } catch (err) {
                console.error('❌ [PREFILL] Error:', err);
                showError('Failed to prefill fusion data: ' + err.message);
            } finally {
                showLoading(false);
            }
        }
    }
}

function renderFusionPool() {
    const container = document.getElementById('fusionPoolContainer');
    const itemsDiv = document.getElementById('fusionPoolItems');
    if (!container || !itemsDiv || !window.fusionPool) return;

    container.style.display = 'block';
    itemsDiv.innerHTML = '';

    window.fusionPool.forEach((item, index) => {
        const itemDiv = document.createElement('div');
        itemDiv.style.cssText = 'background: white; padding: 10px; border-radius: 8px; border: 1px solid #cbd5e1; box-shadow: 0 1px 3px rgba(0,0,0,0.05); min-width: 200px; display: flex; flex-direction: column; gap: 8px;';

        itemDiv.innerHTML = `
            <div style="font-weight: 700; color: #334155; font-size: 13px; border-bottom: 1px solid #f1f5f9; padding-bottom: 5px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;" title="${item.filename}">
                ${index + 1}. ${item.filename}
            </div>
            <div style="display: flex; gap: 5px;">
                <button onclick="assignFromPool(${index}, 'source')" style="flex: 1; padding: 4px; background: #8B4513; color: white; border: none; border-radius: 4px; font-size: 11px; cursor: pointer; font-weight: 600;">Set Source</button>
                <button onclick="assignFromPool(${index}, 'target')" style="flex: 1; padding: 4px; background: #800080; color: white; border: none; border-radius: 4px; font-size: 11px; cursor: pointer; font-weight: 600;">Set Target</button>
            </div>
        `;
        itemsDiv.appendChild(itemDiv);
    });
}

async function assignFromPool(index, type) {
    if (!window.fusionPool || !window.fusionPool[index]) return;

    const item = window.fusionPool[index];
    console.log(`⚡ [POOL] Assigning ${item.filename} to ${type}`);

    showLoading(true);
    try {
        await populatePrefilledSide(item, type);

        // Update header label to show table name
        const headerEl = document.querySelector(`#${type}Parsed h4`);
        if (headerEl) {
            headerEl.innerHTML = `${type === 'source' ? 'Source' : 'Target'} Schema: <span style="font-weight: 400; font-size: 0.9em; color: #666; font-style: italic;">${item.filename}</span>`;
        }

    } finally {
        showLoading(false);
    }
}

async function populatePrefilledSide(item, type) {
    console.log(`⚡ [PREFILL] Populating ${type} with:`, item.filename);

    // Call the parse-text endpoint to get HTML and structured data
    const response = await fetch(API_BASE_URL + '/parse-text', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            text: JSON.stringify(item.data),
            type: type
        })
    });

    const result = await response.json();
    if (result.success) {
        if (type === 'source') {
            sourceData = result.data;
            window.sourceData = sourceData;
            sourcePreviewHTML = result.html || '<p>Data parsed successfully</p>';
            const el = document.getElementById('sourcePreview');
            if (el) el.innerHTML = sourcePreviewHTML;
            const parsed = document.getElementById('sourceParsed');
            if (parsed) parsed.style.display = 'block';
        } else {
            targetData = result.data;
            window.targetData = targetData;
            targetPreviewHTML = result.html || '<p>Data parsed successfully</p>';
            const el = document.getElementById('targetPreview');
            if (el) el.innerHTML = targetPreviewHTML;
            const parsed = document.getElementById('targetParsed');
            if (parsed) parsed.style.display = 'block';
        }

        // Trigger UI updates
        if (typeof updateControls === 'function') updateControls();

        // Ensure data is visible if toggled
        const checkbox = document.getElementById(type + 'DataToggle');
        if (checkbox && checkbox.checked) {
            updateTableDataDisplay(type, true);
        }
    } else {
        throw new Error(result.error || `Failed to process ${type} table`);
    }
}
