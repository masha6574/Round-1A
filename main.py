import fitz
import json
import os
import re
from collections import Counter

try:
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.abspath(os.path.join(script_dir, ".."))
except NameError:
    script_dir = os.getcwd()
    project_root = script_dir

INPUT_DIR = os.path.join(project_root, "input")
OUTPUT_DIR = os.path.join(project_root, "output")


def find_document_title(doc):
    """
    Extracts the title by finding the largest font size on the first page.
    This is more robust than concatenating various text blocks.
    """
    page_one = doc.load_page(0)
    blocks = page_one.get_text("dict", sort=True)["blocks"]

    max_font_size = 0
    title_candidates = []

    for block in blocks:
        if block.get("lines"):
            for line in block["lines"]:
                for span in line["spans"]:
                    if span["size"] > max_font_size:
                        max_font_size = span["size"]

    for block in blocks:
        if block["bbox"][3] < page_one.rect.height * 0.7 and block.get("lines"):
            for line in block["lines"]:
                for span in line["spans"]:
                    if abs(span["size"] - max_font_size) < 1:
                        title_candidates.append(span["text"].strip())

    if not title_candidates:
        return "Untitled Document"

    full_title = " ".join(dict.fromkeys(title_candidates))
    full_title = re.sub(r"\s+", " ", full_title).strip()
    return full_title


def process_pdf(pdf_path):
    doc = fitz.open(pdf_path)
    if not doc.page_count:
        return {"title": "Empty Document", "outline": []}

    title = find_document_title(doc)
    outline = []
    processed_texts = {title.lower()}

    sizes = Counter(
        round(span["size"])
        for page in doc
        for block in page.get_text("dict")["blocks"]
        for line in block.get("lines", [])
        for span in line.get("spans", [])
    )

    if not sizes:
        return {"title": title, "outline": []}

    body_size = sizes.most_common(1)[0][0]

    heading_sizes = sorted([size for size in sizes if size > body_size], reverse=True)
    size_to_level = {size: f"H{i+1}" for i, size in enumerate(heading_sizes[:3])}

    for page_num, page in enumerate(doc):
        page_height = page.rect.height
        clip_box = fitz.Rect(0, page_height * 0.1, page.rect.width, page_height * 0.9)
        blocks = page.get_text("dict", sort=True, clip=clip_box)["blocks"]

        for block in blocks:
            for line in block.get("lines", []):
                line_text = " ".join(span["text"] for span in line["spans"]).strip()
                line_text_lower = line_text.lower()

                if (
                    not line_text
                    or len(line_text) < 3
                    or line_text_lower in processed_texts
                ):
                    continue

                span = line["spans"][0]
                font_size = round(span["size"])
                is_bold = "bold" in span["font"].lower()

                level = None

                match = re.match(
                    r"^\s*(\d+(?:\.\d+)*|Chapter\s\d+|Appendix\s\w)[\.\s-]", line_text
                )
                if match:
                    if is_bold:
                        dot_count = line_text.count(".")
                        level = f"H{min(max(2, dot_count + 2), 4)}"

                if level is None and font_size in size_to_level and is_bold:
                    level = size_to_level[font_size]

                elif (
                    level is None
                    and is_bold
                    and font_size > body_size
                    and len(line_text.split()) < 10
                ):
                    level = "H3"

                if level:

                    clean_text = re.sub(
                        r"^\s*(\d+(?:\.\d+)*|Chapter\s\d+|Appendix\s\w)[\.\s-]*",
                        "",
                        line_text,
                    ).strip()
                    outline.append(
                        {"level": level, "text": clean_text, "page": page_num + 1}
                    )
                    processed_texts.add(line_text_lower)

    doc.close()
    return {"title": title, "outline": outline}


def main():
    """Main function to run the batch processing."""
    if not os.path.exists(INPUT_DIR):
        os.makedirs(INPUT_DIR)
        print(
            f"Created input directory at {INPUT_DIR}. Please add your PDF files there."
        )
        return
    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)

    for filename in os.listdir(INPUT_DIR):
        if filename.lower().endswith(".pdf"):
            pdf_path = os.path.join(INPUT_DIR, filename)
            print(f"🚀 Processing {filename}...")
            try:
                structured_data = process_pdf(pdf_path)
                json_filename = os.path.splitext(filename)[0] + ".json"
                output_path = os.path.join(OUTPUT_DIR, json_filename)

                with open(output_path, "w", encoding="utf-8") as f:
                    json.dump(structured_data, f, indent=4, ensure_ascii=False)

                print(f"Successfully created {output_path}")
            except Exception as e:
                print(f"Failed to process {filename}: {e}")
                import traceback

                traceback.print_exc()


if __name__ == "__main__":
    main()
