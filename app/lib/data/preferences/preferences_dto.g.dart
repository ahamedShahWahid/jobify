// GENERATED CODE - DO NOT MODIFY BY HAND

part of 'preferences_dto.dart';

// **************************************************************************
// JsonSerializableGenerator
// **************************************************************************

PreferencesDto _$PreferencesDtoFromJson(Map<String, dynamic> json) =>
    PreferencesDto(
      desiredRole: $enumDecodeNullable(
          _$DesiredRoleEnumMap, json['desired_role'],
          unknownValue: DesiredRole.unknown),
      locations:
          (json['locations'] as List<dynamic>).map((e) => e as String).toList(),
      expectedCtc: json['expected_ctc'] as String?,
    );

const _$DesiredRoleEnumMap = {
  DesiredRole.softwareEngineering: 'software_engineering',
  DesiredRole.dataAnalytics: 'data_analytics',
  DesiredRole.productManagement: 'product_management',
  DesiredRole.design: 'design',
  DesiredRole.sales: 'sales',
  DesiredRole.marketing: 'marketing',
  DesiredRole.customerSupport: 'customer_support',
  DesiredRole.operations: 'operations',
  DesiredRole.financeAccounting: 'finance_accounting',
  DesiredRole.hrRecruiting: 'hr_recruiting',
  DesiredRole.legal: 'legal',
  DesiredRole.consulting: 'consulting',
  DesiredRole.businessDevelopment: 'business_development',
  DesiredRole.contentCommunications: 'content_communications',
  DesiredRole.administration: 'administration',
  DesiredRole.other: 'other',
  DesiredRole.unknown: 'unknown',
};
