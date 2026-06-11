// SPDX-License-Identifier: LGPL-3.0-only
//
// Smoke widget tests for the Southbrook Kitchen customer app.
// Pure offline checks — no network, no api_client calls. Anything
// that hits the network belongs in a separate integration_test.

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:southbrook_kitchen/screens/login_screen.dart';
import 'package:southbrook_kitchen/services/auth_storage.dart';
import 'package:southbrook_kitchen/theme.dart';
import 'package:southbrook_kitchen/models/project.dart';
import 'package:southbrook_kitchen/models/concept.dart';

void main() {
  testWidgets('LoginScreen renders email/password fields',
      (WidgetTester tester) async {
    await tester.pumpWidget(MaterialApp(
      theme: buildSouthbrookTheme(),
      home: LoginScreen(storage: AuthStorage()),
    ));
    expect(find.text('SOUTHBROOK KITCHEN'), findsOneWidget);
    expect(find.byType(TextField), findsAtLeastNWidgets(2));
    expect(find.text('Sign in'), findsOneWidget);
  });

  test('Project.fromJson tolerates missing optional fields', () {
    final p = Project.fromJson({
      'id': 42,
      'code': 'KP-0042',
      'name': 'Smith Kitchen',
      'state': 'awaiting_customer',
    });
    expect(p.id, 42);
    expect(p.code, 'KP-0042');
    expect(p.state, 'awaiting_customer');
    expect(p.stateLabel, 'Action needed');
    expect(p.theme, isNull);
    expect(p.canUploadPhoto, isFalse);
    expect(p.canReviewConcepts, isFalse);
  });

  test('Project state gates derive correctly', () {
    final draft = Project.fromJson({
      'id': 1, 'code': 'KP-1', 'name': 'X', 'state': 'draft',
    });
    expect(draft.canUploadPhoto, isTrue);
    expect(draft.canApprove, isFalse);

    // Contract keys: detail endpoint sends `concept_ids` + `selected_design_option_id`.
    final ready = Project.fromJson({
      'id': 2, 'code': 'KP-2', 'name': 'Y', 'state': 'awaiting_customer',
      'concept_ids': [11, 12, 13], 'selected_design_option_id': 11,
    });
    expect(ready.designOptionCount, 3);
    expect(ready.selectedOptionId, 11);
    expect(ready.canReviewConcepts, isTrue);
    expect(ready.canApprove, isTrue);

    final done = Project.fromJson({
      'id': 3, 'code': 'KP-3', 'name': 'Z', 'state': 'done',
    });
    expect(done.canUploadPhoto, isFalse);
    expect(done.canApprove, isFalse);
    expect(done.stateLabel, 'Complete');
  });

  test('Concept.fromJson parses numeric price as double', () {
    final c = Concept.fromJson({
      'id': 7,
      'name': 'Concept A',
      'estimated_price': 12500,
      'is_selected': true,
    });
    expect(c.estimatedPrice, 12500.0);
    expect(c.isSelected, isTrue);

    final cFloat = Concept.fromJson({
      'id': 8, 'name': 'Concept B', 'estimated_price': 9999.99,
    });
    expect(cFloat.estimatedPrice, 9999.99);

    final cMissing = Concept.fromJson({'id': 9, 'name': 'Concept C'});
    expect(cMissing.estimatedPrice, isNull);
    expect(cMissing.isSelected, isFalse);
  });

  test('Concept.fromJson reads contract keys and coerces false', () {
    final c = Concept.fromJson({
      'id': 7, 'name': 'Concept A', 'estimated_price': 12500,
      'description_html': '<p>Bright galley</p>', 'preview_attachment_id': 99,
      'is_selected': true,
    });
    expect(c.description, '<p>Bright galley</p>');
    expect(c.previewAttachmentId, 99);
    expect(c.isSelected, isTrue);

    // Odoo sends `false` for empty Char/Many2one — must not throw, must be null.
    final cFalse = Concept.fromJson({
      'id': 8, 'name': 'B', 'description_html': false,
      'estimated_price': false, 'preview_attachment_id': false,
      'placement_data': false,
    });
    expect(cFalse.description, isNull);
    expect(cFalse.estimatedPrice, isNull);
    expect(cFalse.previewAttachmentId, isNull);
    expect(cFalse.placementData, isNull);
  });

  test('Project.fromJson coerces Odoo false-for-empty (regression: C1)', () {
    // The real backend sends `false`, not null/omitted, for empty fields.
    // A raw `as String?` cast would throw TypeError here.
    final p = Project.fromJson({
      'id': 5, 'code': 'KP-5', 'name': 'Empty', 'state': 'draft',
      'theme': false, 'date_target': false, 'date_completed': false,
      'selected_design_option_id': false, 'concept_count': false,
    });
    expect(p.theme, isNull);
    expect(p.dateTarget, isNull);
    expect(p.dateCompleted, isNull);
    expect(p.selectedOptionId, isNull);
    expect(p.designOptionCount, 0);
  });

  test('SouthbrookColors.stateChip maps every known state', () {
    for (final state in [
      'draft', 'designing', 'awaiting_customer', 'approved',
      'in_production', 'done', 'cancelled', 'unknown_state',
    ]) {
      expect(SouthbrookColors.stateChip(state), isNotNull,
          reason: 'state=$state must have a chip color');
    }
  });
}
