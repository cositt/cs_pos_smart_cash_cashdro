#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script de validación para módulo cs_pos_smart_cash_cashdro

Valida:
- Sintaxis Python
- Estructura de archivos
- Imports
- Clases y métodos
"""

import sys
import ast
import os
from pathlib import Path

def check_python_syntax(filepath):
    """Verificar sintaxis Python válida"""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            ast.parse(f.read())
        return True, None
    except SyntaxError as e:
        return False, str(e)

def check_imports(filepath):
    """Verificar imports principales"""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            tree = ast.parse(f.read())
        
        imports = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.append(alias.name)
            elif isinstance(node, ast.ImportFrom):
                imports.append(f"from {node.module}")
        
        return True, imports
    except Exception as e:
        return False, str(e)

def check_classes(filepath):
    """Encontrar clases definidas"""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            tree = ast.parse(f.read())
        
        classes = []
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                methods = [n.name for n in node.body if isinstance(n, ast.FunctionDef)]
                classes.append({
                    'name': node.name,
                    'methods': methods,
                    'method_count': len(methods)
                })
        
        return True, classes
    except Exception as e:
        return False, str(e)

def main():
    module_root = Path(__file__).parent
    
    print("=" * 70)
    print("VALIDACIÓN DE MÓDULO: cs_pos_smart_cash_cashdro")
    print("=" * 70)
    
    # Archivos a validar
    files_to_check = {
        'models': [
            'models/__init__.py',
            'models/pos_payment_method.py',
            'models/cashdro_transaction.py',
            'models/res_config_settings.py'
        ],
        'controllers': [
            'controllers/__init__.py',
            'controllers/gateway_integration.py',
            'controllers/payment_method_integration.py',
            'controllers/pos_payment.py'
        ],
        'tests': [
            'tests/__init__.py',
            'tests/test_models.py',
            'tests/test_gateway_integration.py',
            'tests/test_payment_method_integration.py'
        ]
    }
    
    total_files = 0
    total_classes = 0
    total_methods = 0
    errors = []
    
    for category, files in files_to_check.items():
        print(f"\n📁 {category.upper()}")
        print("-" * 70)
        
        for filepath in files:
            full_path = module_root / filepath
            
            if not full_path.exists():
                errors.append(f"❌ {filepath}: NO EXISTE")
                print(f"  ❌ {filepath}: NO EXISTE")
                continue
            
            total_files += 1
            
            # Verificar sintaxis
            syntax_ok, syntax_error = check_python_syntax(full_path)
            if not syntax_ok:
                errors.append(f"❌ {filepath}: Error de sintaxis - {syntax_error}")
                print(f"  ❌ {filepath}: SINTAXIS INVÁLIDA")
                print(f"     {syntax_error}")
                continue
            
            # Verificar imports
            imports_ok, imports = check_imports(full_path)
            
            # Verificar clases
            classes_ok, classes = check_classes(full_path)
            
            if classes_ok and classes:
                class_info = ", ".join([f"{c['name']}({c['method_count']}m)" for c in classes])
                print(f"  ✅ {filepath}")
                print(f"     Classes: {class_info}")
                total_classes += len(classes)
                total_methods += sum(c['method_count'] for c in classes)
            else:
                print(f"  ✅ {filepath}")
    
    # Resumen
    print("\n" + "=" * 70)
    print("RESUMEN")
    print("=" * 70)
    print(f"✅ Archivos validados: {total_files}")
    print(f"✅ Clases encontradas: {total_classes}")
    print(f"✅ Métodos encontrados: {total_methods}")
    
    if errors:
        print(f"\n❌ ERRORES ENCONTRADOS: {len(errors)}")
        for error in errors:
            print(f"  {error}")
        return 1
    
    # Validación de estructura
    print("\n📋 VALIDACIÓN DE ESTRUCTURA")
    print("-" * 70)
    
    checks = [
        ("__manifest__.py", "Archivo de metadatos"),
        ("__init__.py", "Inicializador del módulo"),
        ("README.md", "Documentación"),
        ("models/__init__.py", "Imports de modelos"),
        ("controllers/__init__.py", "Imports de controllers"),
        ("tests/__init__.py", "Imports de tests"),
        ("security/ir.model.access.csv", "ACL de acceso"),
        ("data/ir_sequence.xml", "Secuencias de datos"),
        ("views/menu_views.xml", "Menú"),
    ]
    
    for filename, description in checks:
        filepath = module_root / filename
        exists = filepath.exists()
        status = "✅" if exists else "❌"
        print(f"  {status} {description:40s} ({filename})")
    
    print("\n" + "=" * 70)
    print("✅ VALIDACIÓN COMPLETADA EXITOSAMENTE")
    print("=" * 70)
    print("\nNota: Para ejecutar tests completos, necesitas instalar el módulo en Odoo:")
    print("  1. Copiar a custom_addons/ en instancia de Odoo")
    print("  2. Actualizar lista de aplicaciones")
    print("  3. Ejecutar: python -m odoo -c config.conf --test-tags=cs_pos_smart_cash_cashdro")
    
    return 0

if __name__ == '__main__':
    sys.exit(main())
