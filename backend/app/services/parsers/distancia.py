import logging
from typing import Any, ClassVar

import pandas as pd

from app.services.parsers.base import BaseExcelParser

logger = logging.getLogger(__name__)


class DistanciaParser(BaseExcelParser):
    CANONICAL_MAP: ClassVar[dict[str, str]] = {
        "cat": "nombre_cat",
        "programa": "nombre_programa",
        "semestre": "semestre",
        "grupo": "grupo",
        "codigo_curso": "cod_curso",
        "curso": "nombre_curso",
        "docente": "nombre_docente",
        "cedula": "doc_docente",
        "correo_institucional": "email_docente",
        "correo_personal": "email_personal",
        "perfil_del_docente": "docente_perfil",
    }

    @classmethod
    def read_excel(cls, file_path: str) -> pd.DataFrame:
        raw = pd.read_excel(file_path, header=None, dtype=str)
        expected_keys = set(cls.CANONICAL_MAP.keys())

        for i, row in raw.iterrows():
            normalized = {
                cls._normalize_column_name(str(v))
                for v in row if pd.notna(v)
            }
            matches = len(expected_keys & normalized)
            if matches >= 5:
                return pd.read_excel(file_path, header=i, dtype=str)

        logger.warning(
            "No se detectó fila de encabezados en '%s', "
            "se asume primera fila como encabezado.",
            file_path,
        )
        return pd.read_excel(file_path, dtype=str)

    @classmethod
    def parse(cls, df: pd.DataFrame, modalidad: str) -> dict[str, Any]:
        df = cls._normalize_columns(df)
        df = cls._filter_confirmed_rows(df)
        df = cls._filter_virtual_rows(df)
        df = cls._parse_program_name(df)
        df = cls._clean_data(df)

        categories_map, courses, users, enrolments, duplicates = cls._process_rows(df, modalidad)
        users_list = list(users.values())
        categories_list = cls._sort_categories(list(categories_map.values()))

        return {
            "categories": categories_list,
            "courses": courses,
            "users": users_list,
            "enrolments": enrolments,
            "duplicates": duplicates,
        }

    @classmethod
    def _process_rows(
        cls, df: pd.DataFrame, modalidad: str
    ) -> tuple[dict, list, dict, list, list]:
        categories_map: dict = {}
        courses: list = []
        users: dict = {}
        enrolments: list = []
        duplicates: list = []

        categories_map[modalidad] = {
            "name": "IDEAD",
            "idnumber": modalidad,
            "parent": 0,
        }

        for _, row in df.iterrows():
            nombre_cat = str(row.get("nombre_cat", "")).strip().upper()
            cat_prefix = cls._build_cat_prefix(nombre_cat)
            cod_prog = cls._build_cod_prog(row)
            semestre_romano = cls._parse_semestre(row)
            grupo = cls._sanitize_group(str(row.get("grupo", "")).strip())
            cedula = str(row.get("doc_docente", "")).strip()

            course_data = cls._build_course_data(
                row, cat_prefix, cod_prog, semestre_romano, grupo, cedula,
            )
            courses.append(course_data)

            cls._ensure_categories(
                categories_map, modalidad, cat_prefix, cod_prog,
                semestre_romano, nombre_cat, row,
            )

            cls._process_teacher(
                row, course_data["shortname"], cedula, nombre_cat,
                users, enrolments, duplicates,
            )

        return categories_map, courses, users, enrolments, duplicates

    @staticmethod
    def _sanitize_group(grupo: str) -> str:
        """Reemplaza caracteres que rompen el patrón SIAUGESMAT (ej. '_' → '-')."""
        import re
        if not grupo:
            return grupo
        return re.sub(r"_+", "-", grupo)

    @staticmethod
    def _build_cat_prefix(nombre_cat: str) -> str:
        if not nombre_cat:
            return "SIN"
        return "URA" if nombre_cat == "APARTADO" else (
            nombre_cat[:3].upper() if len(nombre_cat) >= 3 else nombre_cat.upper()
        )

    @classmethod
    def _build_cod_prog(cls, row) -> str:
        cod_prog = str(row.get("cod_programa", "")).strip()
        if not cod_prog:
            logger.warning("Programa sin código, se usa '0000'.")
            return "0000"
        if cod_prog.isdigit() and len(cod_prog) < 4:
            cod_prog = cod_prog.zfill(4)
        return cod_prog

    @classmethod
    def _parse_semestre(cls, row) -> str:
        semestre = str(row.get("semestre", "")).strip().upper()
        if not semestre:
            semestre = "1"
        return cls._to_roman_numeral(semestre)

    @staticmethod
    def _build_course_data(
        row, cat_prefix: str, cod_prog: str, semestre_romano: str,
        grupo: str, cedula: str,
    ) -> dict:
        cod_curso = str(row.get("cod_curso", "")).strip()
        nombre_curso = str(row.get("nombre_curso", "")).strip()
        cedula_suffix = f"_{cedula}" if cedula else ""
        shortname = (
            f"{cat_prefix}_{cod_prog}_s{semestre_romano}_{cod_curso}"
            f"_G-{grupo}{cedula_suffix}"
        )
        if len(shortname) > 255:
            logger.warning(f"Shortname excede 255 caracteres: {shortname[:80]}... (longitud={len(shortname)})")
        fullname = f"{nombre_curso} - GRUPO {grupo}".upper() if nombre_curso else f"CURSO {cod_curso} - GRUPO {grupo}".upper()
        cat_idnumber = f"{cat_prefix}_{cod_prog}_s{semestre_romano}"
        template = f"PORTAFOLIO_{cod_prog}_s{semestre_romano}_{cod_curso}" if cod_curso else None
        return {
            "shortname": shortname,
            "fullname": fullname,
            "category_idnumber": cat_idnumber,
            "format": "onetopic",
            "templatecourse": template,
            "visible": 1,
            "delete": False,
        }

    @classmethod
    def _ensure_categories(
        cls, categories_map: dict, modalidad: str,
        cat_prefix: str, cod_prog: str, semestre_romano: str,
        nombre_cat: str, row,
    ):
        cat1_idnumber = cat_prefix
        if cat1_idnumber not in categories_map:
            categories_map[cat1_idnumber] = {
                "name": nombre_cat,
                "idnumber": cat1_idnumber,
                "parent": modalidad,
            }

        nombre_prog = cls._clean_program_name(str(row.get("nombre_programa", ""))).upper()
        if not nombre_prog:
            nombre_prog = cod_prog
        cat2_idnumber = f"{cat_prefix}_{cod_prog}"
        if cat2_idnumber not in categories_map:
            categories_map[cat2_idnumber] = {
                "name": nombre_prog,
                "idnumber": cat2_idnumber,
                "parent": cat1_idnumber,
            }

        cat3_idnumber = f"{cat_prefix}_{cod_prog}_s{semestre_romano}"
        if cat3_idnumber not in categories_map:
            categories_map[cat3_idnumber] = {
                "name": f"SEMESTRE {semestre_romano}",
                "idnumber": cat3_idnumber,
                "parent": cat2_idnumber,
            }

    @classmethod
    def _process_teacher(
        cls, row, shortname: str, cedula: str, nombre_cat: str,
        users: dict, enrolments: list, duplicates: list,
    ):
        email = str(row.get("email_docente", "")).strip().lower()
        nombre_docente = str(row.get("nombre_docente", "")).strip()
        if email.endswith("@ut.edu.co") and nombre_docente:
            username = email.split("@")[0]
            if not username:
                return
            firstname, lastname = cls._split_name(nombre_docente)
            if not firstname or not lastname:
                logger.warning("Nombre docente no válido para %s: '%s'", email, nombre_docente)
                return
            if username not in users:
                users[username] = {
                    "username": username,
                    "firstname": firstname,
                    "lastname": lastname,
                    "email": email,
                    "email_personal": str(row.get("email_personal", "")).strip(),
                    "cedula": cedula,
                    "password": "",
                    "city": nombre_cat,
                    "description": str(row.get("docente_perfil", "")).strip(),
                    "delete": False,
                }
            else:
                logger.warning(
                    "Email duplicado detectado: %s. Se conservan datos del primer registro.", email
                )
                duplicates.append({
                    "email": email,
                    "username": username,
                    "course_shortname": shortname,
                })
            enrolments.append({
                "username": username,
                "course_shortname": shortname,
                "role": "editingteacher",
            })
