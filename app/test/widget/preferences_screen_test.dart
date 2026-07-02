import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:go_router/go_router.dart';
import 'package:jobify_app/data/preferences/preferences_dto.dart';
import 'package:jobify_app/data/preferences/preferences_repository.dart';
import 'package:jobify_app/data/preferences/preferences_repository_impl.dart';
import 'package:jobify_app/data/preferences/preferences_update_dto.dart';
import 'package:jobify_app/data/resume/resume_dto.dart';
import 'package:jobify_app/data/resume/resume_parse_status.dart';
import 'package:jobify_app/presentation/preferences/preferences_screen.dart';

class _CapturingRepo implements PreferencesRepository {
  PreferencesUpdateDto? captured;
  @override
  Future<PreferencesDto> fetch() async =>
      const PreferencesDto(desiredRole: null, locations: [], expectedCtc: null);
  @override
  Future<PreferencesDto> update(PreferencesUpdateDto update) async {
    captured = update;
    return fetch();
  }
}

class _ThrowingRepo implements PreferencesRepository {
  @override
  Future<PreferencesDto> fetch() async => throw Exception('boom');
  @override
  Future<PreferencesDto> update(PreferencesUpdateDto update) async =>
      throw Exception('boom');
}

ResumeDto _resumeWithParsed() => ResumeDto(
      id: 'r1',
      applicantId: 'a1',
      originalFilename: 'cv.pdf',
      contentType: 'application/pdf',
      sizeBytes: 1,
      parseStatus: ResumeParseStatus.parsed,
      parsedJson: const {
        'name': 'Ada Lovelace',
        'skills': ['Python', 'SQL'],
      },
      createdAt: DateTime(2026),
    );

Future<void> _pump(
  WidgetTester tester, {
  required PreferencesRepository repo,
  ResumeDto? resume,
}) async {
  final router = GoRouter(
    routes: [
      GoRoute(
        path: '/',
        builder: (_, __) => PreferencesScreen(resume: resume),
      ),
    ],
  );
  await tester.pumpWidget(
    ProviderScope(
      overrides: [preferencesRepositoryProvider.overrideWithValue(repo)],
      child: MaterialApp.router(routerConfig: router),
    ),
  );
  await tester.pumpAndSettle();
}

void main() {
  testWidgets('shows parsed résumé summary', (tester) async {
    await _pump(tester, repo: _CapturingRepo(), resume: _resumeWithParsed());
    expect(find.text('Ada Lovelace'), findsOneWidget);
    expect(find.text('Python'), findsOneWidget);
  });

  testWidgets('shows fallback when resume has no parsed data', (tester) async {
    final resume = ResumeDto(
      id: 'r1',
      applicantId: 'a1',
      originalFilename: 'cv.pdf',
      contentType: 'application/pdf',
      sizeBytes: 1,
      parseStatus: ResumeParseStatus.failed,
      createdAt: DateTime(2026),
    );
    await _pump(tester, repo: _CapturingRepo(), resume: resume);
    expect(find.textContaining("couldn't read your résumé"), findsOneWidget);
  });

  testWidgets('adds a location and saves', (tester) async {
    final repo = _CapturingRepo();
    await _pump(tester, repo: repo, resume: _resumeWithParsed());

    await tester.enterText(
      find.widgetWithText(TextField, 'Add location'),
      'Pune',
    );
    await tester.tap(find.byIcon(Icons.add));
    await tester.pump();
    expect(find.text('Pune'), findsOneWidget);

    await tester.tap(find.widgetWithText(FilledButton, 'Save'));
    await tester.pumpAndSettle();

    expect(repo.captured, isNotNull);
    expect(repo.captured!.locations, ['Pune']);
  });

  testWidgets('skip navigates away without saving', (tester) async {
    final repo = _CapturingRepo();
    await _pump(tester, repo: repo, resume: _resumeWithParsed());
    await tester.tap(find.widgetWithText(TextButton, 'Skip'));
    await tester.pumpAndSettle();
    expect(repo.captured, isNull);
  });

  testWidgets('fetch error shows Retry and keeps Skip available',
      (tester) async {
    await _pump(tester, repo: _ThrowingRepo(), resume: _resumeWithParsed());
    expect(find.text('Retry'), findsOneWidget);
    expect(find.text('Skip'), findsOneWidget);
    // The form never renders off a failed fetch — saving a half-seeded
    // form would clear server-side values.
    expect(find.text('Save'), findsNothing);
    expect(find.text('Locations'), findsNothing);
  });
}
