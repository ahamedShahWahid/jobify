import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:kpa_app/data/resume/resume_dto.dart';
import 'package:kpa_app/data/resume/resume_parse_status.dart';
import 'package:kpa_app/data/resume/resume_repository.dart';
import 'package:kpa_app/data/resume/resume_repository_impl.dart';
import 'package:kpa_app/presentation/resume/resume_screen.dart';

class _Repo implements ResumeRepository {
  _Repo(this._current);
  final ResumeDto? _current;

  @override
  Future<ResumeDto?> current() async => _current;

  @override
  Future<ResumeDto> upload({
    required List<int> bytes,
    required String filename,
    required String contentType,
  }) async =>
      throw UnimplementedError();
}

ResumeDto _dto(ResumeParseStatus s) => ResumeDto(
      id: 'r1',
      applicantId: 'a1',
      originalFilename: 'cv.pdf',
      contentType: 'application/pdf',
      sizeBytes: 1,
      parseStatus: s,
      createdAt: DateTime(2026),
    );

Future<void> _pump(WidgetTester tester, ResumeDto? current) async {
  await tester.pumpWidget(
    ProviderScope(
      overrides: [resumeRepositoryProvider.overrideWithValue(_Repo(current))],
      child: const MaterialApp(home: ResumeScreen()),
    ),
  );
  await tester.pumpAndSettle();
}

void main() {
  testWidgets('empty state shows prompt + upload button', (tester) async {
    await _pump(tester, null);
    expect(find.textContaining('No r\xe9sum\xe9 yet'), findsOneWidget);
    expect(find.text('Upload / Replace r\xe9sum\xe9'), findsOneWidget);
  });

  testWidgets('parsed resume shows filename + Ready chip', (tester) async {
    await _pump(tester, _dto(ResumeParseStatus.parsed));
    expect(find.text('cv.pdf'), findsOneWidget);
    expect(find.text('Ready'), findsOneWidget);
  });

  testWidgets('failed resume shows error chip', (tester) async {
    await _pump(tester, _dto(ResumeParseStatus.failed));
    expect(find.text("Couldn't parse — try again"), findsOneWidget);
  });

  testWidgets('parsing resume shows processing chip', (tester) async {
    await _pump(tester, _dto(ResumeParseStatus.parsing));
    expect(find.text('Processing…'), findsOneWidget);
  });
}
