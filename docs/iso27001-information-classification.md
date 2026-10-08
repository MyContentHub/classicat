# ISO 27001 信息分类相关章节

> 标准版本：ISO/IEC 27001:2022（附录 A）及 ISO/IEC 27002:2022（实施指南）

## 核心控制条款

| 条款 | 名称 | 内容 |
|------|------|------|
| A.5.12 | Classification of information（信息分类） | 组织应根据保密性、完整性、可用性及相关方要求，对信息进行分类 |
| A.5.13 | Labelling of information（信息标记） | 应按信息分类方案制定并实施适当的标记程序 |

## A.5.12 Classification of information（信息分类）

### 控制描述

Information should be classified according to the information security needs of the organization based on confidentiality, integrity, availability and relevant interested party requirements.

（组织应根据信息对组织的重要性，按照保密性、完整性、可用性及相关方要求对信息进行分类。）

### 目的

确保根据信息对组织的重要性，识别和理解信息的保护需求。

### 实施要点（ISO 27002 指南）

- 建立信息分类的专项策略，并传达给所有相关方。
- 分类方案应考虑保密性、完整性、可用性要求，以及业务共享/限制需求和法律要求。
- 信息所有者对分类负责；分类结果应随信息生命周期中价值、敏感度和关键性的变化而更新。
- 分类方案应与访问控制策略保持一致，并在整个组织内统一。
- 组织间信息共享时，应约定如何识别和解释对方的分类级别。

### 其他说明（四级分类示例）

按泄露影响划分四个保密级别：

1. 泄露不造成损害
2. 泄露造成轻微声誉损害或轻微运营影响
3. 泄露对运营或业务目标有重大短期影响
4. 泄露对长期业务目标有严重影响或威胁组织生存

过度分类会导致不必要的安全开销，欠分类则保护不足，需权衡。

## A.5.13 Labelling of information（信息标记）

### 控制描述

An appropriate set of procedures for information labelling should be developed and implemented in accordance with the information classification scheme adopted by the organization.

（应根据组织采用的信息分类方案，制定并实施适当的信息标记程序。）

### 目的

促进信息分类的传达，支持信息处理和管理的自动化。

### 实施要点（ISO 27002 指南）

- 标记程序应覆盖所有格式的信息及相关资产（纸质、电子、通信等）。
- 标记应反映 A.5.12 建立的分类方案。
- 数字文件应嵌入元数据标签，便于自动化系统（如 DLP）识别和处理。
- 可定义例外场景（如公开信息无需标记）以减轻负担。
- 应对员工进行标记方法和接收已标记信息的培训。

## 相关条款

| 条款 | 名称 | 与分类的关系 |
|------|------|------|
| A.5.14 | Information transfer（信息传递） | 传递信息时按分类级别执行相应的保护措施 |
| A.5.15 | Access control（访问控制） | 访问权限基于信息分类级别 |

## 旧版对照（ISO 27001:2013）

| 2013 版 | 2022 版 |
|------|------|
| A.8.2 Information classification | A.5.12 |
| A.8.3 Information labelling | A.5.13 |

## 来源

- [ISO/IEC 27001:2022 官方页面](https://www.iso.org/standard/82875.html)
- [A.5.12 & A.5.13 详解（Pretesh Biswas）](https://preteshbiswas.com/2023/01/04/iso-270012022-a-5-12-classification-of-information-a-5-13-labeling-of-information/)
- [A.5.13 Labelling of Information（High Table）](https://hightable.io/iso-27001-annex-a-5-13-labelling-of-information/)
