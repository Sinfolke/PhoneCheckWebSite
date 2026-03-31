import base64
import difflib
from typing import List, Dict, Union, Any

import cv2
import numpy as np
from pydantic import BaseModel, Field
from rapidocr_onnxruntime import RapidOCR
from sklearn.cluster import DBSCAN

from models.OCR import OCRBox
from huggingface_hub import hf_hub_download
from rapidfuzz import fuzz
import re

# det_path = hf_hub_download("monkt/paddleocr-onnx", "detection/v5/det.onnx")
# rec_path = hf_hub_download("monkt/paddleocr-onnx", "languages/eslav/rec.onnx")
# dict_path = hf_hub_download("monkt/paddleocr-onnx", "languages/eslav/dict.txt")

print("Загрузка RapidOCR (ONNX)...")
ocr_reader = RapidOCR(
    # det_model_path=det_path,
    # rec_model_path=rec_path,
    # rec_keys_path=dict_path
)
print("RapidOCR готов к молниеносной работе!")

class ReadSettings(BaseModel):
    title: str = ""
    exact_setting_structure: List[Union[OCRBox, Dict[str, List[OCRBox]]]] = Field(default_factory=list)
    texts: List[OCRBox] = Field(default_factory=list)
    values: Dict[str, List[OCRBox]] = Field(default_factory=dict)
    @staticmethod
    def clean_text(text: str):
        text = text.strip()

        # добавить пробелы между словами если склеились
        text = re.sub(r'([а-яіїєґ])([А-ЯІЇЄҐ])', r'\1 \2', text)

        # убрать двойные пробелы
        text = re.sub(r'\s+', ' ', text)

        return text

    @classmethod
    def from_base64(cls, base64_string: str, ocr_reader: RapidOCR):
        def merge_nearby_words(line: List[OCRBox], img_w: int) -> List[OCRBox]:
            if not line:
                return []

            line = sorted(line, key=lambda b: b.x)
            merged = [line[0]]

            for box in line[1:]:
                last = merged[-1]

                gap = box.x - (last.x + last.w)

                # если слова близко друг к другу, считаем их одной фразой
                if gap < img_w * 0.03:
                    new_x = min(last.x, box.x)
                    new_y = min(last.y, box.y)
                    new_w = max(last.x + last.w, box.x + box.w) - new_x
                    new_h = max(last.y + last.h, box.y + box.h) - new_y

                    merged[-1] = OCRBox(
                        text=f"{last.text} {box.text}",
                        x=new_x,
                        y=new_y,
                        w=new_w,
                        h=new_h
                    )
                else:
                    merged.append(box)

            return merged
        def score_boxes(boxes):
            score = 0
            for b in boxes:
                t = b.text

                # штраф за мусор
                if len(t) <= 2:
                    continue

                # бонус за цифры (IMEI, даты и т.д.)
                if any(c.isdigit() for c in t):
                    score += 20

                # бонус за нормальные слова
                score += len(t)

            return score

        def build_boxes(results) -> List[OCRBox]:
            boxes: List[OCRBox] = []
            if not results:
                return boxes

            for line in results:
                bbox, text = line[0], line[1]

                if not text:
                    continue

                cleaned = cls.clean_text(str(text))
                if not cleaned:
                    continue

                xs = [int(p[0]) for p in bbox]
                ys = [int(p[1]) for p in bbox]

                boxes.append(OCRBox(
                    text=cleaned,
                    x=min(xs),
                    y=min(ys),
                    w=max(xs) - min(xs),
                    h=max(ys) - min(ys)
                ))
            return boxes

        def merge_boxes(items: List[OCRBox]) -> OCRBox:
            return OCRBox(
                text=" ".join(x.text for x in items),
                x=min(x.x for x in items),
                y=min(x.y for x in items),
                w=max(x.x + x.w for x in items) - min(x.x for x in items),
                h=max(x.y + x.h for x in items) - min(x.y for x in items),
            )

        def is_probable_value_text(text: str) -> bool:
            t = text.strip().lower()
            if not t:
                return False
            if any(ch.isdigit() for ch in t):
                return True
            if "%" in t:
                return True
            if len(t) <= 2:
                return False
            return True

        def looks_like_key(box: OCRBox, next_line: List[OCRBox] | None = None) -> bool:
            text = box.text.strip()
            if not text:
                return False

            t = text.lower()

            # ключ обычно не состоит только из цифр
            if t.isdigit():
                return False

            # ключ обычно не содержит процент как основное значение
            if "%" in t and len(t) <= 6:
                return False

            # ключ обычно длиннее 2 символов
            if len(t) <= 2:
                return False

            # ключ часто состоит из буквенных слов
            alpha_count = sum(ch.isalpha() for ch in t)
            digit_count = sum(ch.isdigit() for ch in t)

            if alpha_count == 0:
                return False

            # если цифр больше, чем букв — это скорее значение
            if digit_count > alpha_count:
                return False

            # если есть следующая строка, ключ часто выше нее по высоте
            if next_line:
                next_merged = merge_boxes(next_line)
                if box.h < next_merged.h * 0.9:
                    return False

            return True
        obj = cls()

        if "," in base64_string:
            base64_string = base64_string.split(",", 1)[1]

        img_data = base64.b64decode(base64_string)
        nparr = np.frombuffer(img_data, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

        if img is None:
            raise ValueError("Не удалось декодировать изображение")

        orig_h, orig_w = img.shape[:2]

        # Умеренный resize
        max_dim = 1600
        scale = min(1.0, max_dim / max(orig_h, orig_w))
        if scale < 1.0:
            img = cv2.resize(
                img,
                (int(orig_w * scale), int(orig_h * scale)),
                interpolation=cv2.INTER_AREA
            )

        img_h, img_w = img.shape[:2]

        # Для маленьких изображений можно слегка увеличить
        if max(img_h, img_w) < 900:
            img = cv2.resize(
                img,
                None,
                fx=1.2,
                fy=1.2,
                interpolation=cv2.INTER_CUBIC
            )
            img_h, img_w = img.shape[:2]

        variants = [
            ("orig", img),
            ("gray", cv2.cvtColor(img, cv2.COLOR_BGR2GRAY))
        ]

        best_boxes: List[OCRBox] = []
        best_score = -1
        best_name = ""

        for name, candidate in variants:
            try:
                results, _ = ocr_reader(candidate)
                boxes = build_boxes(results)

                # Простой скор: больше боксов + больше символов
                score = score_boxes(boxes)

                if score > best_score:
                    best_score = score
                    best_boxes = boxes
                    best_name = name
            except Exception:
                continue

        boxes = best_boxes

        if not boxes:
            return obj

        print("Best OCR mode:", best_name)

        boxes.sort(key=lambda b: (b.y, b.x))

        # --- 6. Group lines by Y ---
        points = np.array([[box.y + box.h / 2] for box in boxes], dtype=np.float32)
        eps = max(6, int(img_h * 0.008))
        clustering = DBSCAN(eps=eps, min_samples=1).fit(points)

        lines = {}
        for label, box in zip(clustering.labels_, boxes):
            lines.setdefault(int(label), []).append(box)

        grouped_lines = list(lines.values())
        grouped_lines.sort(key=lambda line: min(b.y for b in line))

        for line in grouped_lines:
            line.sort(key=lambda b: b.x)

        for i in range(len(grouped_lines)):
            grouped_lines[i] = merge_nearby_words(grouped_lines[i], img_w)
        # --- 7. Title detection ---
        top_area = img_h * 0.22
        top_boxes = [b for b in boxes if b.y < top_area]

        if top_boxes:
            # лучше учитывать не только высоту, но и ширину
            title_box = max(top_boxes, key=lambda b: (b.h * b.w, b.h))
            obj.title = title_box.text

        # --- 8. Build structure ---
        used_lines = set()

        for i, line in enumerate(grouped_lines):
            if i in used_lines:
                continue

            # пропускаем заголовок, если строка состоит только из него
            if obj.title and len(line) == 1 and line[0].text == obj.title:
                continue

            # CASE 1: горизонтальная пара
            # Пример: "Стан батареї   100%"
            if len(line) >= 2:
                gaps = [
                    line[j].x - (line[j - 1].x + line[j - 1].w)
                    for j in range(1, len(line))
                ]

                if gaps:
                    # Общая ширина строки по box'ам
                    line_left = min(part.x for part in line)
                    line_right = max(part.x + part.w for part in line)
                    line_width = max(1, line_right - line_left)

                    # Более разумные пороги
                    avg_gap = sum(gaps) / len(gaps)
                    max_gap = max(gaps)
                    split_idx = gaps.index(max_gap) + 1

                    key_parts = line[:split_idx]
                    value_parts = line[split_idx:]

                    key_box = merge_boxes(key_parts)
                    value_box = merge_boxes(value_parts)

                    # Разрыв должен быть заметным:
                    # - либо существенно больше среднего
                    # - либо просто не слишком маленьким относительно строки/картинки
                    large_enough_gap = (
                            max_gap > avg_gap * 1.8 or
                            max_gap > img_w * 0.05 or
                            max_gap > line_width * 0.12
                    )

                    # Значение должно быть справа от ключа
                    correct_order = value_box.x > key_box.x + key_box.w * 0.8

                    # Правая часть реально похожа на value
                    value_ok = is_probable_value_text(value_box.text)

                    if large_enough_gap and correct_order and value_ok:
                        obj.values[key_box.text] = value_parts
                        obj.exact_setting_structure.append({key_box.text: value_parts})
                        continue

            # CASE 2: вертикальная пара
            if i + 1 < len(grouped_lines) and (i + 1) not in used_lines:
                next_line = grouped_lines[i + 1]

                if len(line) == 1 and len(next_line) >= 1:
                    key = line[0]
                    next_first = next_line[0]

                    aligned = abs(key.x - next_first.x) < img_w * 0.12
                    vertical_gap = next_first.y - (key.y + key.h)
                    close_y = -5 < vertical_gap < key.h * 2.8

                    key_ok = looks_like_key(key, next_line)

                    if aligned and close_y and key_ok:
                        obj.values[key.text] = next_line
                        obj.exact_setting_structure.append({key.text: next_line})
                        used_lines.add(i + 1)
                        continue

            # CASE 3: обычный текст
            obj.texts.extend(line)
            if len(line) == 1:
                obj.exact_setting_structure.append(line[0])
            else:
                obj.exact_setting_structure.append(line)
        print(f"values: {obj.values}")
        return obj
    def locate(self, yaml_dict: dict, paths: list[str]) -> dict[str, OCRBox]:
        best_matches: dict[str, OCRBox] = {}

        for path in paths:
            keys = path.split('.')
            target_node = yaml_dict

            for k in keys:
                target_node = target_node.get(k)
                if target_node is None:
                    raise KeyError(f"Путь '{path}' не найден в конфиге")
            key = target_node.get("name", "")
            expected_name = key.strip().lower()

            best_match = None
            best_ratio = 0.0
            for ocr_key_text, text_list in self.values.items():
                ocr_key_text = ocr_key_text.strip().lower()
                ratio: float
                if expected_name == ocr_key_text:
                    ratio = 100
                else:
                    ratio = fuzz.token_set_ratio(expected_name, ocr_key_text)
                if ratio >= 60 and ratio > best_ratio:
                    best_ratio = ratio
                    best_match = text_list  # Берем весь список слов значения
                print(f"label {ocr_key_text} for {expected_name}: ratio {ratio}; best_ratio: {best_ratio}")
            if best_match:
                # МАГИЯ СКЛЕИВАНИЯ:
                # Если OCR разбил значение на части ["4000", "mAh", "(typical)"],
                # мы склеиваем их в один большой прямоугольник и одну строку!
                merged_text = " ".join(b.text for b in best_match)

                min_x = min(b.x for b in best_match)
                min_y = min(b.y for b in best_match)
                max_w = max(b.x + b.w for b in best_match) - min_x
                max_h = max(b.y + b.h for b in best_match) - min_y

                merged_box = OCRBox(text=merged_text, x=min_x, y=min_y, w=max_w, h=max_h)
                best_matches[key] = merged_box
            else:
                raise KeyError(f"Поле '{expected_name}' не найдено на экране.")

        return best_matches