# Template Breakdown Documentation

## Overview
The monolithic `index.html` (5888 lines) has been broken down into modular, maintainable components.

## New Structure

```
sender/
├── static/
│   ├── css/
│   │   └── styles.css          # All CSS styles (~826 lines)
│   └── js/
│       └── main.js              # All JavaScript (~4556 lines)
├── templates/
│   ├── base.html                # Base template with CSS/JS includes
│   ├── index.html               # NEW: Main template using includes
│   ├── index_old.html           # Backup of monolithic version
│   ├── index_backup_original.html  # Original backup
│   └── components/
│       ├── header.html          # App header section
│       ├── upload_section.html  # File upload interface
│       ├── parsed_content.html  # Schema preview area
│       ├── controls.html        # Processing controls & pipeline config
│       └── results.html         # Results display area
└── main_fast.py                 # Updated with static file serving
```

## What Changed

### Before (Monolithic)
- **Single file**: 5888 lines
- **index.html**: HTML + CSS + JavaScript all inline
- **Memory impact**: Entire file loaded into Claude Code context
- **Maintenance**: Hard to find and edit specific sections

### After (Modular)
- **7 component files**: Each focused on a specific UI section
- **Separated concerns**: CSS, JS, and HTML in separate files
- **Memory efficient**: Only load specific components when needed
- **Easy maintenance**: Find and edit sections quickly

## File Breakdown

### 1. **base.html** (13 lines)
Main template with:
- HTML structure
- Links to external CSS/JS
- Block definitions for content

### 2. **index.html** (19 lines)
Extends base.html and includes:
- All component includes
- Loading/error/success states

### 3. **Components**
- **header.html** (4 lines): App title and description
- **upload_section.html** (29 lines): Source/target file upload UI
- **parsed_content.html** (27 lines): Schema preview with data toggles
- **controls.html** (~265 lines): Pipeline configuration, match/merge controls
- **results.html** (~99 lines): Results tabs and display containers

### 4. **Static Assets**
- **styles.css** (~826 lines): All styling from inline `<style>` tag
- **main.js** (~4555 lines): All JavaScript from inline `<script>` tag

## Benefits

### 1. **Reduced Memory Usage**
- Claude Code no longer needs to load entire 5888-line file
- Can read individual components (4-265 lines each)
- Dramatically reduces token/context usage

### 2. **Better Organization**
- Each component has a single responsibility
- Easy to locate specific UI sections
- Clear separation of concerns

### 3. **Easier Maintenance**
- Edit CSS without touching HTML/JS
- Update one component without affecting others
- Reduced merge conflicts in version control

### 4. **Reusability**
- Components can be reused in other templates
- Base template can be extended for new pages
- CSS/JS shared across all pages

## How to Use

### Editing a Component
```bash
# Edit just the header
edit templates/components/header.html

# Edit just the CSS
edit static/css/styles.css

# Edit just the upload section
edit templates/components/upload_section.html
```

### Adding a New Component
1. Create file in `templates/components/`
2. Add include in `templates/index.html`:
   ```html
   {% include 'components/your_component.html' %}
   ```

### Creating a New Page
1. Create new template extending base:
   ```html
   {% extends "base.html" %}
   {% block content %}
       <!-- Your content -->
   {% endblock %}
   ```

## Rollback Instructions

If you need to revert to the monolithic version:

```bash
cd templates
mv index.html index_modular.html
mv index_old.html index.html
```

Or use the original backup:
```bash
cd templates
cp index_backup_original.html index.html
```

## Testing

1. **Start the server:**
   ```bash
   python main_fast.py
   # or
   uvicorn main_fast:app --reload --port 8000
   ```

2. **Access the app:**
   - Open browser: `http://localhost:8000/fuze/`

3. **Verify:**
   - CSS loads correctly
   - JavaScript works
   - All UI sections display properly
   - File uploads work
   - Processing pipeline functions

## Troubleshooting

### CSS/JS Not Loading
- Check static files exist in `static/css/` and `static/js/`
- Verify FastAPI has mounted static files (main_fast.py:31)
- Check browser console for 404 errors

### Component Not Displaying
- Verify file exists in `templates/components/`
- Check include path in `index.html`
- Look for template syntax errors

### Jinja2 Template Errors
- Check all `{% %}` tags are properly closed
- Verify indentation in template files
- Check for missing `endblock` statements

## Performance Improvement

**Context Usage Comparison:**

| File | Old Size | New Size | Reduction |
|------|----------|----------|-----------|
| index.html | 5888 lines | 19 lines | **99.7%** |
| Header | N/A | 4 lines | Isolated |
| Upload | N/A | 29 lines | Isolated |
| Parsed Content | N/A | 27 lines | Isolated |
| Controls | N/A | 265 lines | Isolated |
| Results | N/A | 99 lines | Isolated |

**Total lines when editing specific component:**
- **Before**: Always 5888 lines
- **After**: 4-265 lines per component

## Notes

- All original functionality preserved
- No changes to API endpoints
- No changes to JavaScript logic
- CSS classes remain the same
- Component breakdown follows semantic UI sections
