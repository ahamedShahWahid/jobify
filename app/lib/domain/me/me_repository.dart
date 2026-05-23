import 'package:kpa_app/data/me/me_dto.dart';

export 'package:kpa_app/data/me/me_dto.dart'
    show MeDto, ApplicantSummaryDto;

abstract interface class MeRepository {
  Future<MeDto> fetch();
}
