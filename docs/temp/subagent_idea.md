我想通过SubAgent的编译器根据一段最佳实践的文档描述，来生成对应的SubAgent对应的配置，这个配置可以人为地后期调整，到时候建立SubAgent的时候，就可以直接加载这个配置生成SubAgent的实例即可

SubAgent编译器工具原理大致如下：
1. 读取最佳实践的文档描述，读取系统里所有的工具清单（ToolCatalog + MCP），并读取 skills 作为提示词约束
2. 解析文档，提取出SubAgent的相关配置信息，这里面包含了SubAgent的名称、能力描述、系统提示词、工具集（tool_name）等
3. 生成对应的SubAgent配置文件

