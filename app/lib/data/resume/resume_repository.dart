import 'package:jobify_app/data/resume/resume_dto.dart';

abstract interface class ResumeRepository {
  /// The applicant's latest resume, or null if none uploaded.
  Future<ResumeDto?> current();

  Future<ResumeDto> upload({
    required List<int> bytes,
    required String filename,
    required String contentType,
  });
}
