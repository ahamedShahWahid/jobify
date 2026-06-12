import 'package:jobify_app/data/consents/consent_dto.dart';

abstract interface class ConsentsRepository {
  Future<ConsentListResponse> list();
  Future<ConsentDto> patch(String scope, {required bool granted});
}
