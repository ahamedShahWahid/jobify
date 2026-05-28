import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:kpa_app/core/error/exceptions.dart';
import 'package:kpa_app/data/resume/resume_dto.dart';
import 'package:kpa_app/data/resume/resume_parse_status.dart';
import 'package:kpa_app/data/resume/resume_repository.dart';
import 'package:kpa_app/data/resume/resume_repository_impl.dart';
import 'package:kpa_app/presentation/resume/resume_controller.dart';

ResumeDto _dto(String id, ResumeParseStatus s) => ResumeDto(
      id: id,
      applicantId: 'a1',
      originalFilename: 'cv.pdf',
      contentType: 'application/pdf',
      sizeBytes: 1,
      parseStatus: s,
      createdAt: DateTime(2026),
    );

class _Repo implements ResumeRepository {
  _Repo({this.initial, this.fail = false});
  ResumeDto? initial;
  final bool fail;
  @override
  Future<ResumeDto?> current() async => initial;
  @override
  Future<ResumeDto> upload({
    required List<int> bytes,
    required String filename,
    required String contentType,
  }) async {
    if (fail) throw const ApiException(statusCode: 413, slug: 'too_large');
    return _dto('new', ResumeParseStatus.pending);
  }
}

void main() {
  test('build loads current resume', () async {
    final c = ProviderContainer(
      overrides: [
        resumeRepositoryProvider.overrideWithValue(
          _Repo(initial: _dto('r1', ResumeParseStatus.parsed)),
        ),
      ],
    );
    addTearDown(c.dispose);
    final v = await c.read(resumeControllerProvider.future);
    expect(v?.id, 'r1');
  });

  test('upload success sets the new resume as state', () async {
    final c = ProviderContainer(
      overrides: [
        resumeRepositoryProvider.overrideWithValue(_Repo()),
      ],
    );
    addTearDown(c.dispose);
    await c.read(resumeControllerProvider.future);
    final ok = await c.read(resumeControllerProvider.notifier).uploadFromPicked(
      bytes: const [1],
      filename: 'cv.pdf',
      contentType: 'application/pdf',
    );
    expect(ok, isTrue);
    expect(
      c.read(resumeControllerProvider).value?.parseStatus,
      ResumeParseStatus.pending,
    );
  });

  test('upload error returns false + error state', () async {
    final c = ProviderContainer(
      overrides: [
        resumeRepositoryProvider.overrideWithValue(_Repo(fail: true)),
      ],
    );
    addTearDown(c.dispose);
    await c.read(resumeControllerProvider.future);
    final ok = await c.read(resumeControllerProvider.notifier).uploadFromPicked(
      bytes: const [1],
      filename: 'cv.pdf',
      contentType: 'application/pdf',
    );
    expect(ok, isFalse);
    expect(c.read(resumeControllerProvider).hasError, isTrue);
  });
}
