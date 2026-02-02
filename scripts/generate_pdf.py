"""
Script to convert markdown walkthrough to PDF with diagrams
Uses fpdf2 for PDF generation - works on Windows without GTK dependencies
"""

from fpdf import FPDF
import re
import os

class PDFReport(FPDF):
    def __init__(self):
        super().__init__()
        self.add_font('DejaVu', '', 'C:/Windows/Fonts/arial.ttf', uni=True)
        self.add_font('DejaVu', 'B', 'C:/Windows/Fonts/arialbd.ttf', uni=True)
        self.add_font('DejaVu', 'I', 'C:/Windows/Fonts/ariali.ttf', uni=True)
        self.add_font('Consolas', '', 'C:/Windows/Fonts/consola.ttf', uni=True)
        
    def header(self):
        self.set_font('DejaVu', 'I', 9)
        self.set_text_color(100, 100, 100)
        self.cell(0, 10, 'Map Management Feature - Complete Analysis', 0, 1, 'C')
        self.ln(5)
        
    def footer(self):
        self.set_y(-15)
        self.set_font('DejaVu', 'I', 8)
        self.set_text_color(100, 100, 100)
        self.cell(0, 10, f'Page {self.page_no()}/{{nb}}', 0, 0, 'C')
        
    def chapter_title(self, title, level=1):
        if level == 1:
            self.set_font('DejaVu', 'B', 20)
            self.set_text_color(26, 26, 46)
            self.ln(10)
            self.cell(0, 12, title, 0, 1, 'L')
            self.set_draw_color(255, 107, 53)
            self.set_line_width(1)
            self.line(10, self.get_y(), 200, self.get_y())
            self.ln(8)
        elif level == 2:
            self.set_font('DejaVu', 'B', 16)
            self.set_text_color(22, 33, 62)
            self.ln(8)
            self.cell(0, 10, title, 0, 1, 'L')
            self.set_draw_color(74, 144, 164)
            self.set_line_width(0.5)
            self.line(10, self.get_y(), 150, self.get_y())
            self.ln(5)
        elif level == 3:
            self.set_font('DejaVu', 'B', 13)
            self.set_text_color(15, 52, 96)
            self.ln(5)
            self.cell(0, 8, title, 0, 1, 'L')
            self.ln(3)
        else:
            self.set_font('DejaVu', 'B', 11)
            self.set_text_color(26, 26, 46)
            self.ln(3)
            self.cell(0, 7, title, 0, 1, 'L')
            self.ln(2)
            
    def body_text(self, text):
        self.set_font('DejaVu', '', 10)
        self.set_text_color(51, 51, 51)
        self.multi_cell(0, 6, text)
        self.ln(2)
        
    def code_block(self, code, language=''):
        self.set_fill_color(45, 45, 45)
        self.set_text_color(248, 248, 242)
        self.set_font('Consolas', '', 8)
        
        # Add padding
        self.ln(3)
        y_start = self.get_y()
        
        # Split code into lines and write
        lines = code.strip().split('\n')
        for line in lines:
            # Escape special chars
            line = line.replace('\\', '\\\\')
            if self.get_y() > 270:
                self.add_page()
            self.set_x(15)
            self.cell(180, 5, line[:100], 0, 1, 'L', True)
        
        self.ln(3)
        self.set_text_color(51, 51, 51)
        
    def mermaid_diagram(self, code):
        """Render mermaid diagram as a styled box"""
        self.ln(5)
        
        # Draw gradient-like header
        self.set_fill_color(102, 126, 234)
        self.rect(10, self.get_y(), 190, 12, 'F')
        self.set_font('DejaVu', 'B', 11)
        self.set_text_color(255, 255, 255)
        self.set_xy(15, self.get_y() + 3)
        self.cell(0, 6, '📊 Architecture Diagram (Mermaid)', 0, 1)
        
        # Draw code box
        self.set_y(self.get_y() + 5)
        self.set_fill_color(250, 250, 250)
        self.set_text_color(51, 51, 51)
        self.set_font('Consolas', '', 8)
        
        lines = code.strip().split('\n')
        for line in lines:
            if self.get_y() > 260:
                self.add_page()
            self.set_x(15)
            self.cell(180, 5, line[:95], 0, 1, 'L', True)
            
        # Note
        self.ln(2)
        self.set_font('DejaVu', 'I', 8)
        self.set_text_color(100, 100, 100)
        self.cell(0, 5, 'Tip: Open the .md file in VS Code or a Mermaid viewer for interactive diagrams', 0, 1, 'C')
        self.ln(5)
        
    def table(self, headers, rows):
        """Draw a table"""
        self.ln(3)
        
        # Calculate column widths
        num_cols = len(headers)
        col_width = 180 / num_cols
        
        # Header row
        self.set_fill_color(255, 107, 53)
        self.set_text_color(255, 255, 255)
        self.set_font('DejaVu', 'B', 9)
        
        for header in headers:
            self.cell(col_width, 8, str(header)[:20], 1, 0, 'C', True)
        self.ln()
        
        # Data rows
        self.set_font('DejaVu', '', 8)
        self.set_text_color(51, 51, 51)
        
        fill = False
        for row in rows:
            if self.get_y() > 260:
                self.add_page()
                # Redraw header
                self.set_fill_color(255, 107, 53)
                self.set_text_color(255, 255, 255)
                self.set_font('DejaVu', 'B', 9)
                for header in headers:
                    self.cell(col_width, 8, str(header)[:20], 1, 0, 'C', True)
                self.ln()
                self.set_font('DejaVu', '', 8)
                self.set_text_color(51, 51, 51)
                
            self.set_fill_color(248, 249, 250) if fill else self.set_fill_color(255, 255, 255)
            for cell in row:
                cell_text = str(cell)[:25] if cell else ''
                self.cell(col_width, 7, cell_text, 1, 0, 'L', True)
            self.ln()
            fill = not fill
            
        self.ln(5)
        
    def bullet_list(self, items):
        self.set_font('DejaVu', '', 10)
        self.set_text_color(51, 51, 51)
        for item in items:
            self.set_x(15)
            self.cell(5, 6, '•', 0, 0)
            self.multi_cell(175, 6, item)
        self.ln(2)


def parse_markdown_to_pdf(md_content, pdf):
    """Parse markdown content and add to PDF"""
    
    lines = md_content.split('\n')
    i = 0
    
    while i < len(lines):
        line = lines[i]
        
        # Skip empty lines
        if not line.strip():
            i += 1
            continue
            
        # Headers
        if line.startswith('# '):
            pdf.chapter_title(line[2:].strip(), 1)
        elif line.startswith('## '):
            pdf.chapter_title(line[3:].strip(), 2)
        elif line.startswith('### '):
            pdf.chapter_title(line[4:].strip(), 3)
        elif line.startswith('#### '):
            pdf.chapter_title(line[5:].strip(), 4)
            
        # Mermaid code blocks
        elif line.strip().startswith('```mermaid'):
            code_lines = []
            i += 1
            while i < len(lines) and not lines[i].strip().startswith('```'):
                code_lines.append(lines[i])
                i += 1
            pdf.mermaid_diagram('\n'.join(code_lines))
            
        # Regular code blocks
        elif line.strip().startswith('```'):
            lang = line.strip()[3:]
            code_lines = []
            i += 1
            while i < len(lines) and not lines[i].strip().startswith('```'):
                code_lines.append(lines[i])
                i += 1
            pdf.code_block('\n'.join(code_lines), lang)
            
        # Tables
        elif line.strip().startswith('|') and i + 1 < len(lines) and '---' in lines[i + 1]:
            # Parse table
            headers = [h.strip() for h in line.split('|')[1:-1]]
            i += 2  # Skip header and separator
            rows = []
            while i < len(lines) and lines[i].strip().startswith('|'):
                row = [c.strip() for c in lines[i].split('|')[1:-1]]
                rows.append(row)
                i += 1
            pdf.table(headers, rows)
            continue
            
        # Horizontal rules
        elif line.strip() == '---':
            pdf.ln(5)
            pdf.set_draw_color(200, 200, 200)
            pdf.line(10, pdf.get_y(), 200, pdf.get_y())
            pdf.ln(5)
            
        # Bullet lists
        elif line.strip().startswith('- ') or line.strip().startswith('* '):
            items = [line.strip()[2:]]
            i += 1
            while i < len(lines) and (lines[i].strip().startswith('- ') or lines[i].strip().startswith('* ')):
                items.append(lines[i].strip()[2:])
                i += 1
            pdf.bullet_list(items)
            continue
            
        # Numbered lists
        elif re.match(r'^\d+\.', line.strip()):
            items = [re.sub(r'^\d+\.\s*', '', line.strip())]
            i += 1
            while i < len(lines) and re.match(r'^\d+\.', lines[i].strip()):
                items.append(re.sub(r'^\d+\.\s*', '', lines[i].strip()))
                i += 1
            # Use bullet list for now
            for idx, item in enumerate(items, 1):
                pdf.set_x(15)
                pdf.set_font('DejaVu', '', 10)
                pdf.cell(8, 6, f'{idx}.', 0, 0)
                pdf.multi_cell(172, 6, item)
            pdf.ln(2)
            continue
            
        # Regular text
        elif line.strip():
            # Clean up markdown formatting
            text = line.strip()
            text = re.sub(r'\*\*(.*?)\*\*', r'\1', text)  # Bold
            text = re.sub(r'\*(.*?)\*', r'\1', text)  # Italic
            text = re.sub(r'`(.*?)`', r'\1', text)  # Inline code
            text = re.sub(r'\[(.*?)\]\(.*?\)', r'\1', text)  # Links
            if text:
                pdf.body_text(text)
        
        i += 1


# Main execution
if __name__ == '__main__':
    markdown_file = r"C:\Users\HP\.gemini\antigravity\brain\e1f1bcc6-d39f-46a2-91d3-df1f0c48e63c\walkthrough.md"
    output_pdf = r"C:\Users\HP\.gemini\antigravity\brain\e1f1bcc6-d39f-46a2-91d3-df1f0c48e63c\Map_Management_Walkthrough.pdf"
    
    print("📄 Reading markdown file...")
    with open(markdown_file, 'r', encoding='utf-8') as f:
        md_content = f.read()
    
    print("🔨 Creating PDF...")
    pdf = PDFReport()
    pdf.alias_nb_pages()
    pdf.add_page()
    
    parse_markdown_to_pdf(md_content, pdf)
    
    print("💾 Saving PDF...")
    pdf.output(output_pdf)
    
    file_size = os.path.getsize(output_pdf) / 1024
    print(f"\n✅ PDF generated successfully!")
    print(f"📄 Output: {output_pdf}")
    print(f"📏 File size: {file_size:.1f} KB")
