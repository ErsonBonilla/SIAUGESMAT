from abc import ABC, abstractmethod
from typing import Any, ClassVar

import pandas as pd

from app.services.category_utils import sort_categories


class BaseExcelParser(ABC):
    CANONICAL_MAP: ClassVar[dict[str, str]] = {}
    IGNORE_PREFIXES = ("total_", "horas_")
    IGNORE_EXACT: ClassVar[set[str]] = {
        "categoria",
        "tipo_programa",
        "tipo_vinculacion",
        "nivel",
        "perfil_del_curso",
    }

    @classmethod
    @abstractmethod
    def read_excel(cls, file_path: str) -> pd.DataFrame: ...

    @classmethod
    @abstractmethod
    def parse(cls, df: pd.DataFrame, modalidad: str) -> dict[str, Any]: ...

    @staticmethod
    def _normalize_column_name(name: str) -> str:
        import re

        name = name.lower().strip()
        accent_map = str.maketrans(
            {
                "á": "a",
                "é": "e",
                "í": "i",
                "ó": "o",
                "ú": "u",
                "ü": "u",
                "ñ": "n",
            }
        )
        name = name.translate(accent_map)
        name = re.sub(r"[.\-/\\'´`()]+", "_", name)
        name = re.sub(r"\s+", "_", name)
        name = re.sub(r"[^a-z0-9_]", "", name)
        name = re.sub(r"_+", "_", name)
        return name.strip("_")

    @classmethod
    def _normalize_columns(cls, df: pd.DataFrame) -> pd.DataFrame:
        seen = set()
        rename = {}
        for col in df.columns:
            normalized = cls._normalize_column_name(str(col))
            if not normalized or normalized in cls.IGNORE_EXACT:
                continue
            if any(normalized.startswith(p) for p in cls.IGNORE_PREFIXES):
                continue
            canonical = cls.CANONICAL_MAP.get(normalized)
            if canonical and canonical not in seen:
                seen.add(canonical)
                rename[col] = canonical
        return df.rename(columns=rename)

    @classmethod
    def _filter_confirmed_rows(cls, df: pd.DataFrame) -> pd.DataFrame:
        confirma_col = None
        for col in df.columns:
            if cls._normalize_column_name(str(col)) == "confirma":
                confirma_col = col
                break

        if not confirma_col:
            raise ValueError(
                "No se encontró la columna 'Confirma' en el archivo. "
                "Esta columna es obligatoria para procesar la carga académica."
            )

        before = len(df)
        mask = df[confirma_col].astype(str).str.strip().str.upper() == "ACEPTA"
        df = df[mask].copy()
        df = df.drop(columns=[confirma_col])

        descartadas = before - len(df)
        if descartadas:
            import logging

            logging.getLogger(__name__).info(
                "Confirma: %d → %d filas (%d descartadas por no tener ACEPTA)",
                before,
                len(df),
                descartadas,
            )
        else:
            import logging

            logging.getLogger(__name__).info("Confirma: todas las %d filas están ACEPTA", len(df))

        return df

    @classmethod
    def _filter_virtual_rows(cls, df: pd.DataFrame) -> pd.DataFrame:
        observaciones_col = None
        for col in df.columns:
            if cls._normalize_column_name(str(col)) == "observaciones":
                observaciones_col = col
                break

        if not observaciones_col:
            raise ValueError(
                "No se encontró la columna 'Observaciones' en el archivo. "
                "Esta columna es obligatoria para procesar la carga académica."
            )

        before = len(df)
        mask = df[observaciones_col].astype(str).str.contains("virtual", case=False, na=False)
        df = df[~mask].copy()
        df = df.drop(columns=[observaciones_col])

        descartadas = before - len(df)
        if descartadas:
            import logging

            logging.getLogger(__name__).info(
                "Observaciones: %d → %d filas (%d descartadas por virtualidad)",
                before,
                len(df),
                descartadas,
            )
        else:
            import logging

            logging.getLogger(__name__).info("Observaciones: todas las %d filas continúan", len(df))

        return df

    @classmethod
    def _parse_program_name(cls, df: pd.DataFrame) -> pd.DataFrame:
        if "cod_programa" not in df.columns and "nombre_programa" in df.columns:
            mask = df["nombre_programa"].str.contains(r"^\d+\s*-\s*", na=False)
            if mask.any():
                parts = df.loc[mask, "nombre_programa"].str.split(r"\s*-\s*", n=1, expand=True)
                df.loc[mask, "cod_programa"] = parts[0].str.strip()
                df.loc[mask, "nombre_programa"] = parts[1].str.strip()
            if "cod_programa" not in df.columns:
                df["cod_programa"] = ""
            else:
                df["cod_programa"] = df["cod_programa"].fillna("")
        return df

    @staticmethod
    def _clean_data(df: pd.DataFrame) -> pd.DataFrame:
        for col in [
            "nombre_cat",
            "cod_programa",
            "cod_curso",
            "semestre",
            "grupo",
            "nombre_curso",
            "nombre_programa",
            "nombre_docente",
            "email_docente",
            "email_personal",
            "doc_docente",
            "docente_perfil",
        ]:
            if col in df.columns:
                df[col] = df[col].fillna("").astype(str)
        return df

    @staticmethod
    def _clean_program_name(raw: str) -> str:
        import re

        cleaned = re.sub(r"[\d-]", "", raw)
        return re.sub(r"\s+", " ", cleaned).strip()

    # ----------------------------------------------------------------
    # Conjuntos para partición de nombres colombianos
    # Convención: [APELLIDO(S)] [NOMBRE(S)]
    # ----------------------------------------------------------------
    _GIVEN_NAMES: ClassVar[set[str]] = {
        "ADIELA",
        "ADOLFO",
        "ADRIANA",
        "AGUSTIN",
        "AGUSTÍN",
        "AINHOA",
        "ALBA",
        "ALBEIRO",
        "ALBERTO",
        "ALEJANDRA",
        "ALEJANDRO",
        "ALEXANDER",
        "ALFREDO",
        "ALICIA",
        "ALVARO",
        "ÁLVARO",
        "AMALIA",
        "AMANDA",
        "AMPARO",
        "ANA",
        "ANDRES",
        "ANDRÉS",
        "ANDREA",
        "ANGEL",
        "ÁNGEL",
        "ANGELA",
        "ÁNGELA",
        "ANGIE",
        "ANTONIA",
        "ANTONIO",
        "ARACELY",
        "ARLES",
        "ARTURO",
        "BEATRIZ",
        "BENITO",
        "BERTHA",
        "BIBIANA",
        "BLANCA",
        "CAMILA",
        "CAMILO",
        "CARLA",
        "CARLOS",
        "CARMEN",
        "CATALINA",
        "CELIA",
        "CESAR",
        "CÉSAR",
        "CLARA",
        "CLAUDIA",
        "CLAUDIO",
        "CONSTANZA",
        "CRISTINA",
        "DANIEL",
        "DANIELA",
        "DAVID",
        "DAYANA",
        "DENISSE",
        "DIANA",
        "DIEGO",
        "DOLORES",
        "DOMINGO",
        "DORA",
        "DORIAN",
        "DUBAN",
        "EDGAR",
        "EDILMA",
        "EDINSON",
        "EDUARDO",
        "EDWIN",
        "ELENA",
        "ELIZABETH",
        "ELKIN",
        "ENCARNACION",
        "ENCARNACIÓN",
        "ENRIQUE",
        "ESNEIDER",
        "ESPERANZA",
        "ESTEBAN",
        "ESTHER",
        "EVA",
        "FABIO",
        "FANNY",
        "FELIPE",
        "FERNANDO",
        "FLOR",
        "FRANCISCA",
        "FRANCISCO",
        "GABRIEL",
        "GEMA",
        "GERMAN",
        "GERMÁN",
        "GISSELLE",
        "GLADIS",
        "GLORIA",
        "GONZALO",
        "GRACIELA",
        "GUILLERMO",
        "GUSTAVO",
        "HAROLD",
        "HECTOR",
        "HÉCTOR",
        "HENRY",
        "HERMES",
        "HUGO",
        "IGNACIO",
        "IRENE",
        "ISABEL",
        "IVAN",
        "IVÁN",
        "JAIME",
        "JAVIER",
        "JEFFERSON",
        "JENNIFER",
        "JENNY",
        "JESUS",
        "JESÚS",
        "JIMMY",
        "JOAQUIN",
        "JOAQUÍN",
        "JOHANNA",
        "JORGE",
        "JOSE",
        "JOSÉ",
        "JOSEFA",
        "JUAN",
        "JULIA",
        "JULIAN",
        "JULIÁN",
        "JULIETH",
        "JULIO",
        "KAREN",
        "KATERINE",
        "KATHERINE",
        "LARA",
        "LAURA",
        "LEYDI",
        "LILIANA",
        "LINA",
        "LISETH",
        "LUCIA",
        "LUCÍA",
        "LUIS",
        "LUISA",
        "LUZ",
        "MAGDA",
        "MANUEL",
        "MARCOS",
        "MARGARITA",
        "MARIA",
        "MARÍA",
        "MARINA",
        "MARITZA",
        "MARTA",
        "MARTIN",
        "MARTÍN",
        "MAURICIO",
        "MAYRA",
        "MERCEDES",
        "MERY",
        "MIGUEL",
        "MILENA",
        "MILTON",
        "MONICA",
        "MÓNICA",
        "MYRIAM",
        "NAIARA",
        "NANCY",
        "NATALIA",
        "NEIDER",
        "NELLY",
        "NELSON",
        "NEREA",
        "NICOLAS",
        "NICOLÁS",
        "NORA",
        "NUBIA",
        "NURIA",
        "OLGA",
        "OSCAR",
        "ÓSCAR",
        "PABLO",
        "PAOLA",
        "PASCUAL",
        "PASTORA",
        "PATRICIA",
        "PAULA",
        "PEDRO",
        "PIEDAD",
        "RAFAEL",
        "RAMON",
        "RAMÓN",
        "RAQUEL",
        "RAUL",
        "RAÚL",
        "RICARDO",
        "ROBERTO",
        "ROBINSON",
        "ROCIO",
        "ROCÍO",
        "ROSA",
        "RUBEN",
        "RUBÉN",
        "RUTH",
        "SANDRA",
        "SANTIAGO",
        "SARA",
        "SEBASTIAN",
        "SEBASTIÁN",
        "SERGIO",
        "SHIRLEY",
        "SILVIA",
        "SOCORRO",
        "SOFIA",
        "SOFÍA",
        "SUSANA",
        "TATIANA",
        "TERESA",
        "TOMAS",
        "TOMÁS",
        "VALENTINA",
        "VALERIA",
        "VERONICA",
        "VERÓNICA",
        "VICENTE",
        "VICTOR",
        "VÍCTOR",
        "VIVIANA",
        "WALTER",
        "WILLIAM",
        "WILSON",
        "YAMID",
        "YANETH",
        "YENIFER",
        "YENNY",
        "YOLANDA",
        "YOLIMA",
        "ZULMA",
    }

    _SURNAME_PARTICLES: ClassVar[set[str]] = {
        "DE",
        "DEL",
        "E",
        "LA",
        "LAS",
        "LOS",
        "VAN",
        "VON",
        "Y",
    }

    @staticmethod
    def _split_name(full_name: str) -> tuple[str, str]:
        import re

        cleaned = re.sub(r"\s+", " ", full_name).strip().upper()
        parts = cleaned.split()
        n = len(parts)

        if n == 0:
            return "", ""
        if n == 1:
            return parts[0].title(), parts[0].title()

        boundary = None
        for i, token in enumerate(parts):
            if token in BaseExcelParser._SURNAME_PARTICLES:
                continue
            if token in BaseExcelParser._GIVEN_NAMES:
                boundary = i
                break

        if boundary is not None and boundary > 0:
            firstname = " ".join(parts[boundary:])
            lastname = " ".join(parts[:boundary])
        elif boundary == 0:
            firstname = " ".join(parts[:1])
            lastname = " ".join(parts[1:])
        elif n == 2:
            firstname = parts[1]
            lastname = parts[0]
        elif n == 3:
            firstname = parts[2]
            lastname = " ".join(parts[:2])
        else:
            firstname = " ".join(parts[2:])
            lastname = " ".join(parts[:2])

        return firstname.title(), lastname.title()

    @staticmethod
    def _to_roman_numeral(value: str) -> str:
        import re

        value = value.strip().upper()

        if re.match(r"^[IVXLCDM]+$", value):
            return value

        if value.isdigit():
            num = int(value)
            if num < 1:
                return value
            numerals = [
                (1000, "M"),
                (900, "CM"),
                (500, "D"),
                (400, "CD"),
                (100, "C"),
                (90, "XC"),
                (50, "L"),
                (40, "XL"),
                (10, "X"),
                (9, "IX"),
                (5, "V"),
                (4, "IV"),
                (1, "I"),
            ]
            result = ""
            for n, roman in numerals:
                while num >= n:
                    result += roman
                    num -= n
            return result

        return value

    _sort_categories = staticmethod(sort_categories)
