// SPDX-License-Identifier: LGPL-3.0-only
//
// Southbrook visual identity. Walnut + sky tokens mirror the Odoo
// portal CSS so screens feel cohesive across mobile and web.

import 'package:flutter/material.dart';

class SouthbrookColors {
  static const walnut = Color(0xFF1E3A5F);
  static const walnutLight = Color(0xFF3D5B81);
  static const sky = Color(0xFF7AA9D6);
  static const linen = Color(0xFFF5EFE6);
  static const ink = Color(0xFF1A1A1A);
  static const inkSoft = Color(0xFF555555);
  static const success = Color(0xFF1F7A3F);
  static const warning = Color(0xFFB45309);
  static const danger = Color(0xFFB42318);
  static const divider = Color(0xFFE5E2DC);

  // State chips — match the sb.kitchen.project state machine.
  static Color stateChip(String? state) {
    switch (state) {
      case 'draft':
        return inkSoft;
      case 'designing':
        return walnutLight;
      case 'awaiting_customer':
        return const Color(0xFFD97706); // amber — action needed
      case 'approved':
      case 'in_production':
        return success;
      case 'done':
        return walnut;
      case 'cancelled':
        return danger;
      default:
        return inkSoft;
    }
  }
}

ThemeData buildSouthbrookTheme() {
  final base = ThemeData(
    colorScheme: ColorScheme.fromSeed(
      seedColor: SouthbrookColors.walnut,
      brightness: Brightness.light,
    ),
    useMaterial3: true,
    scaffoldBackgroundColor: SouthbrookColors.linen,
  );
  return base.copyWith(
    appBarTheme: const AppBarTheme(
      backgroundColor: SouthbrookColors.walnut,
      foregroundColor: Colors.white,
      elevation: 0,
      centerTitle: false,
    ),
    elevatedButtonTheme: ElevatedButtonThemeData(
      style: ElevatedButton.styleFrom(
        backgroundColor: SouthbrookColors.walnut,
        foregroundColor: Colors.white,
        padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 14),
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(6),
        ),
        textStyle: const TextStyle(
          fontSize: 16,
          fontWeight: FontWeight.w600,
        ),
      ),
    ),
    outlinedButtonTheme: OutlinedButtonThemeData(
      style: OutlinedButton.styleFrom(
        foregroundColor: SouthbrookColors.walnut,
        side: const BorderSide(color: SouthbrookColors.walnut),
        padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 14),
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(6),
        ),
      ),
    ),
    cardTheme: CardThemeData(
      color: Colors.white,
      elevation: 0,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(8),
        side: const BorderSide(color: SouthbrookColors.divider),
      ),
      margin: EdgeInsets.zero,
    ),
    dividerColor: SouthbrookColors.divider,
    inputDecorationTheme: InputDecorationTheme(
      border: OutlineInputBorder(
        borderRadius: BorderRadius.circular(6),
        borderSide: const BorderSide(color: SouthbrookColors.divider),
      ),
      focusedBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(6),
        borderSide: const BorderSide(color: SouthbrookColors.walnut, width: 2),
      ),
      filled: true,
      fillColor: Colors.white,
      contentPadding: const EdgeInsets.symmetric(horizontal: 14, vertical: 14),
    ),
    snackBarTheme: const SnackBarThemeData(
      behavior: SnackBarBehavior.floating,
      backgroundColor: SouthbrookColors.walnut,
      contentTextStyle: TextStyle(color: Colors.white),
    ),
  );
}
