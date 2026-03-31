def normalize_imei(value: str) -> str:
    return "".join(ch for ch in value if ch.isdigit())


def luhn_checksum_imei14(imei14: str) -> int:
    if len(imei14) != 14 or not imei14.isdigit():
        raise ValueError("IMEI base must be 14 digits")

    total = 0

    for i, ch in enumerate(imei14):
        digit = int(ch)

        # Для IMEI удваиваются цифры на чётных позициях, если считать с 1
        if (i + 1) % 2 == 0:
            digit *= 2
            if digit > 9:
                digit -= 9

        total += digit

    return (10 - (total % 10)) % 10


def is_valid_imei(imei: str) -> bool:
    imei = normalize_imei(imei)

    if len(imei) != 15:
        return False

    if len(set(imei)) == 1:
        return False

    expected = luhn_checksum_imei14(imei[:14])
    return expected == int(imei[14])