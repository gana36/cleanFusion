"""
Prompt templates for LLM operations

This module contains PROMPT_TEMPLATES dictionary with all prompts for:
- Schema matching (baseline, operator)
- Schema merging
- Instance merging
- Multi-step operations
"""

# --- PROMPT TEMPLATES ---
PROMPT_TEMPLATES = {
    "complex": {
        "baseline": {
            "json_default": {
                "match": """Given are Schema1/Table 1 (source) and Schema2/Table 2 (target) in the [document, json file or images].
Identify the header attributes for the source and target schemas/tables.
Match the similar attributes between the source and target schemas/tables and output the matches in JSON structure:

{
 "matches": [{"source": "attribute_name1", "target": "attribute_name3"}]
}""",
                "merge": """Given are Schema1/Table 1 (source) and Schema2/Table 2 (target) in the [document, json file or images].
Identify the header attributes for the source and target schemas/tables.
Given are the following schemas and their match results:
Source Schema:
{source_schema_placeholder}
Target Schema:
{target_schema_placeholder}
Match Results:
{match_results_placeholder}
Act as a schema merger for hierarchical, non-relational schemas.
Your task is to merge the attributes that are matched between the source1 (Table 1) and a source2 (Table 2) using the match results provided above.

Create a new merged schema (Merged_Schema) from the matched attributes above.
Ensure the merged table includes all matching attributes and values from both source and target schemas.
Output the result in JSON format with the following structure:
{
  "HMD_Merged_Schema": [],
  "VMD_Merged_Schema": [],
  "Merged_Schema": [],
  "Merged_Data": []
}""",
                "instance_merge": """Given are Schema1/Table 1 (source) and Schema2/Table 2 (target) in the [document, json file or images].
Identify the header attributes for the source and target schemas/tables.
Given are the following schemas and their match results:
Source Schema:
{source_schema_placeholder}
Target Schema:
{target_schema_placeholder}
Match Results:
{match_results_placeholder}
Act as a schema merger for hierarchical, non-relational schemas.
Your task is to merge the attributes that are matched between the source1 (Table 1) and a source2 (Table 2) using the match results provided above.

Create a new merged schema (Merged_Schema) from the matched attributes above.
Ensure the merged table includes all matching attributes and values from both source and target schemas.
Output the result in JSON format with the following structure:
{
  "HMD_Merged_Schema": [],
  "VMD_Merged_Schema": [],
  "Merged_Schema": [],
  "Merged_Data": []
}"""
            }
        },
        "operator": {
            "json_default": {
                "match": """-----------------------------------------------------------
Complex Match Operator - Input(schema1 and schema2)
                       - Output(map M)
-----------------------------------------------------------

Convert schema 1 (Table 1) and schema 2(Table 2) into JSON while preserving its structure.
Analyze the data nodes in the JSON for each schema and identify child attributes for each header attribute based on the hierarchical structure within the data node.
For each schema/table, list:
1) Horizontal (HMD) attributes along with their child attributes, if any.
2) Vertical (VMD) attributes along with their child attributes, if applicable.
3) Do not invent any attribute names unless they are present in the original schema.
For each schema/table, follow the JSON structure outlined below.

{
  "Table1.HMD": [
    {
      "attribute1": "Name",
      "children": [
        {
          "child_level1.attribute1": "name"
        },
        {
          "child_level1.attribute2": "name"
        }
        ]
    },
    {
      "attribute2": "Name",
      "children": [
        {
          "child_level1.attribute1": "name"
        },
        {
          "child_level1.attribute2": "name"
        }
        ]
    }
   ],
    "Table1.VMD":[
    {
      "attribute1": "name",
      "children": [
        {
          "child_level1.attribute1": "name"
        },
        {
          "child_level1.attribute2": "name"
        }]
    },
    {
      "attribute2": "name",
      "children": [
        {
          "child_level1.attribute1": "name"
        },
        {
          "child_level1.attribute2": "name"
        }]
    }
}

Given the HMD source schema and HMD target schema from above.

Act as a schema matcher for hierarchical, non-relational schemas.
Your task is to identify semantic matches between a source schema and a target schema by analyzing their nested JSON structure.

Each schema is represented as a hierarchical JSON, where:
- Keys represent attribute hierarchy
- Values specify attribute name (the actual header text from the tables)
- Nested structures ("children") define sub-attributes defined as child_level#, where # is number of levels

IMPORTANT: The schemas provided include the actual attribute names/headers from the source tables. Use these names to understand the semantic meaning and find matches. The attribute values contain the exact text that appears in the table headers.

MATCHING CRITERIA:
Two attributes should be matched if they satisfy ANY of the following conditions:
1. EXACT MATCH: Identical attribute names with possible case variations
2. SYNONYM MATCH: Semantically equivalent terms representing the same concept
3. ABBREVIATION MATCH: Full form matches abbreviated form or acronym
4. HIERARCHICAL MATCH: General category matches specific subtype or specialization
5. CONTEXTUAL MATCH: Attributes representing the same concept in different contexts

For hierarchical matches (parent-child relationships):
- A general category term CAN match specific subtypes or instances of that category
- A parent concept CAN match specialized variations or implementations
- Consider semantic containment: if one term is a type/variant/specialization of another, they should match
- Apply domain knowledge to recognize semantic relationships
- STRICT PARENT-CHILD CONTEXT: Do NOT match identical child attributes (e.g., 'N (%)', 'RR') if their parent attributes represent fundamentally different, unrelated concepts (e.g., 'Chemotherapy' vs 'Patients experiencing RDI'). Parents must be semantically compatible for children to match.

The set of all attribute names is called table schema or metadata. Metadata is a set of attributes of a table. Metadata can be stored in a row or in a column. A table with hierarchical metadata is a complex, non-relational table that, similar to a relational table, has metadata (i.e., attributes), but unlike a relational table it may be found not only in a row, but also in a column. It may also take several rows or columns. Such rows with metadata are called horizontal metadata (HMD).On the other hand, such columns with metadata are called vertical metadata (VMD)

Instructions:
I will first provide the source schema in a hierarchical JSON format.
Then, I will provide the target schema in the same format.
You must analyze the hierarchical relationships and identify semantic matches at all levels.
Sample input JSON for a table (Table1 or Source)  with separate JSON for HMD and VMD
{
  "Table1.HMD": [
    {
      "attribute1": "attribute1name"
    },
    {
      "attribute2": "attribute2name",
      "children": [
        {
          "child_level1attribute1": "child_level1attribute1name",
          "children": [
            {
              "child_level2attribute1": "child_level2attribute1name"
            }
          ]
        }
      ]
    }
  ]
}


{
  "Table1.VMD": [
    {
      "attribute1": "attribute1name"
    },
    {
      "attribute2": "attribute2name",
      "children": [
        {
          "child_level1attribute1": "child_level1attribute1name",
          "children": [
            {
              "child_level2attribute1": "child_level2attribute1name"
            }
          ]
        }
      ]
    }
  ]
}

Provide the output as a structured JSON, following the template
{
  {"HMD_matches": [
    {"source": "attribute1name", "target": "attribute1name"},
    {"source": "attribute2name", "target": ".attribute2name"},
    {"source": "attribute2name.child_level1attribute1name", "target":  "attribute2name.child_level1attribute1name"},
{"source": "attribute2name.child_level1attribute1name.child_level2attribute1name", "target": "attribute2name.child_level1attribute1name.child_level2attribute1name"}
  ]
  },
  {
  "VMD_matches": [
  {"source": "attribute1name", "target": "attribute1name"},
    {"source": "attribute2name", "target": ".attribute2name"},
    {"source": "attribute2name.child_level1attribute1name", "target":  "attribute2name.child_level1attribute1name"},
{"source": "attribute2name.child_level1attribute1name.child_level2attribute1name", "target": "attribute2name.child_level1attribute1name.child_level2attribute1name"}

  ]
}
}
If either HMD or VMD is not present return [] for respective keys.

Example Input (Source Schema):
{
  "Table1.HMD": [
    {
      "attribute1": "name"
    },
    {
      "attribute2": "birth_date",
      "children": [
        {
          "child_level1.attribute1": "date_of_birth",
          "children": [
            {
              "child_level2.attribute1": "dob_formatted"
            }
          ]
        }
      ]
    }
  ]
}

Example Input (Target Schema):

{
  "Table2.HMD": [
    {
      "attribute1": "full_name"
    },
    {
      "attribute2": "dob",
      "children": [
        {
          "child_level1.attribute1": "dob_field",
          "children": [
            {
              "child_level2.attribute1": "formatted_dob"
            }
          ]
        }
      ]
    }
  ]
}

Example Input (Source Schema):
{
  "Table1.HMD": [
    {
      "attribute1": "name"
    },
    {
      "attribute2": "birth_date",
      "children": [
        {
          "child_level1.attribute1": "date_of_birth"
        }
      ]
    }
  ],
  "Table1.VMD": [
    {
      "attribute1": "Personal Info:",
      "children": [
        {
          "child_level1.attribute1": "Age"
        },
        {
          "child_level1.attribute2": "Height"
        }
      ]
    }
  ]
}

Example Input (Target Schema):

{
  "Table2.HMD": [
    {
      "attribute1": "full_name"
    },
    {
      "attribute2": "dob",
      "children": [
        {
          "child_level1.attribute1": "dob_field"
        }
      ]
    }
  ],
  "Table2.VMD": [
    {
      "attribute1": "Personal Information:",
      "children": [
        {
          "child_level1.attribute1": "Age in years"
        },
        {
          "child_level1.attribute2": "Height in cm"
        }
      ]
    }
  ]
}



Expected Output (Schema Matches):


{
  "HMD_matches": [
    {"source": "name", "target": "full_name"},
    {"source": "birth_date", "target": "dob"},
    {"source": "birth_date.date_of_birth", "target": "dob.dob_field"}
  ],
  "VMD_matches": [
    {"source": "Personal Info:", "target": "Personal Information:"},
    {"source": "Personal Info.Age", "target": "Personal Information.Age in years"},
    {"source": "Personal Info.Height", "target": "Personal Information.Height in cm"}
  ]
}

Apply flexible semantic matching using the criteria above. Match attributes that represent the same or related concepts, including hierarchical relationships where a general term corresponds to specific subtypes. Use domain knowledge and context to identify meaningful relationships.


VALIDATION CHECKLIST:
✓ Return ONLY valid JSON (no explanations)
✓ Use exact attribute names from schemas (no modifications)
✓ Include "Table1.HMD."/"Table1.VMD." and "Table2.HMD."/"Table2.VMD." prefixes
✓ Return empty arrays [] if no valid matches exist""",

                "merge": """Given are Table 1 (source1) and Table 2 (source2) in the [document or json file].

Convert schema 1 (Table 1) and schema 2(Table 2) into JSON while preserving its structure.
Analyze the data nodes in the JSON for each schema and identify child attributes for each header attribute based on the hierarchical structure within the data node.
For each schema/table, list:
1) Horizontal (HMD) attributes along with their child attributes, if any.
2) Vertical (VMD) attributes along with their child attributes, if applicable.
3) Do not invent any attribute names unless they are present in the original schema.
For each schema/table, follow the JSON structure outlined below.

{
  "Table1.HMD": [
    {
      "attribute1": "Name",
      "children": [
        {
          "child_level1.attribute1": "name"
        },
        {
          "child_level1.attribute2": "name"
        }
        ]
    },
    {
      "attribute2": "Name",
      "children": [
        {
          "child_level1.attribute1": "name"
        },
        {
          "child_level1.attribute2": "name"
        }
        ]
    }
   ],
    "Table1.VMD":[
    {
      "attribute1": "name",
      "children": [
        {
          "child_level1.attribute1": "name"
        },
        {
          "child_level1.attribute2": "name"
        }]
    },
    {
      "attribute2": "name",
      "children": [
        {
          "child_level1.attribute1": "name"
        },
        {
          "child_level1.attribute2": "name"
        }]
    }
}

Given the HMD source1 schema and HMD target/source2 schema from above.


Act as a schema merger for hierarchical, non-relational schemas.
Your task is to merge the attributes that are matched between the source1 (Table 1) and a source2 (Table 2) using the following match results:

Match Results:
{match_results_placeholder}

Source Schema:
{source_schema_placeholder}

Target Schema:
{target_schema_placeholder}


Create a new merged schema (Merged_Schema) from the matched attributes above.
Add all remaining HMD and VMD attributes and their children from source1 (Schema1/Table1) and source2 (Schema2/Table2) in the new merged schema (Merged_Schema).
CRITICAL RULE: DO NOT DROP OR OMIT ANY COLUMNS OR ROWS. Every single attribute from both origin schemas MUST appear in the Merged_Schema. If an attribute is not part of a match, it must still be added as a standalone attribute.
Output them in JSON format in the following structure:

{
  "HMD_Merged_Schema": ["attr_name.child_attr_name"],
  "VMD_Merged_Schema": ["attr_name", "attr_name.child_attr_name"],
}

Using the merged schema (Merged_Schema), for each HMD attribute in the HMD_Merged_Schema,
go through all the VMD attributes in the VMD_Merged_Schema list and add the corresponding values from source and target tables.
If no values are available, add "".
If HMD attribute has children then skip the attribute and create a list only for the children.
Output them in JSON format in the following structure:
}
"Merged_Data":[
        {"HMD.attr_name.child_name": "value" {
                {"VMD.attr_name.child_name1","source1": "value", "source2":"value"},
                {"VMD.attr_name.child_name2","source1": "value", "source2":"value"}
        }
        ]
}

CRITICAL: ENGLISH ONLY OUTPUT
Ensure all text in the Merged_Data (values) and Merged_Schema (attributes) is in English. 
Translate if necessary.

Create a new map schema (Map_Schema1) that includes only the source1 (Schema1/Table1) attributes contained in the matches mapping.
Output them in JSON format in the following structure:

{
  "HMD_Map_Schema1": [{"source1": "Merged_Schema.attr_name", "source2":"Schema1.attr_name"}],
  "VMD_Map_Schema1": [{"source1": "Merged_Schema.attr_name", "source2":"Schema1.attr_name"}],
}

Create a new map schema (Map_Schema2) that includes only the source2 (Schema2/Table2) attributes contained in the matches mapping.
Output them in JSON format in the following structure:
{
  "HMD_Map_Schema2": [{"source1": "Merged_Schema.attr_name", "source2":"Schema2.attr_name"}],
  "VMD_Map_Schema2": [{"source1": "Merged_Schema.attr_name", "source2":"Schema2.attr_name"}],
}


If no valid matches exist, return: {"Merged_Schema":[]}""",

                "instance_merge": """Given are Table 1 (source1) and Table 2 (source2) in the [document or json file].

Convert schema 1 (Table 1) and schema 2(Table 2) into JSON while preserving its structure.
Analyze the data nodes in the JSON for each schema and identify child attributes for each header attribute based on the hierarchical structure within the data node.
For each schema/table, list:
1) Horizontal (HMD) attributes along with their child attributes, if any.
2) Vertical (VMD) attributes along with their child attributes, if applicable.
3) Do not invent any attribute names unless they are present in the original schema.
For each schema/table, follow the JSON structure outlined below.

{
  "Table1.HMD": [
    {
      "attribute1": "Name",
      "children": [
        {
          "child_level1.attribute1": "name"
        },
        {
          "child_level1.attribute2": "name"
        }
        ]
    },
    {
      "attribute2": "Name",
      "children": [
        {
          "child_level1.attribute1": "name"
        },
        {
          "child_level1.attribute2": "name"
        }
        ]
    }
   ],
    "Table1.VMD":[
    {
      "attribute1": "name",
      "children": [
        {
          "child_level1.attribute1": "name"
        },
        {
          "child_level1.attribute2": "name"
        }]
    },
    {
      "attribute2": "name",
      "children": [
        {
          "child_level1.attribute1": "name"
        },
        {
          "child_level1.attribute2": "name"
        }]
    }
}

Given the HMD source1 schema and HMD target/source2 schema from above.


Act as a schema merger for hierarchical, non-relational schemas.
Your task is to merge the attributes that are matched between the source1 (Table 1) and a source2 (Table 2) using the following match results:

Match Results:
{match_results_placeholder}

Source Schema:
{source_schema_placeholder}

Target Schema:
{target_schema_placeholder}


Create a new merged schema (Merged_Schema) from the matched attributes above.
Add all remaining HMD and VMD attributes and their children from source1 (Schema1/Table1) and source2 (Schema2/Table2) in the new merged schema (Merged_Schema).
CRITICAL RULE: DO NOT DROP OR OMIT ANY COLUMNS OR ROWS. Every single attribute from both origin schemas MUST appear in the Merged_Schema. If an attribute is not part of a match, it must still be added as a standalone attribute.
VERY IMPORTANT: For all unmapped/remaining attributes that have a hierarchical structure, you MUST output their full dot-separated path (e.g., Parent.Child) in the schema, exactly like you do for matches. DO NOT output just the child name.
Output them in JSON format in the following structure:
And please dont put Predictor in the HMD_Merged_Schema
{
  "HMD_Merged_Schema": ["Parent.Child", "Standalone_Column"],
  "VMD_Merged_Schema": ["Parent.Child", "Standalone_Row"],
}

CRITICAL - Extracting Actual Data Values:
You MUST populate Merged_Data with the ACTUAL CELL VALUES from both source tables.
For each HMD column and VMD row combination:
- Find the cell value in Source Schema's "data" field and put it in "source1"
- Find the cell value in Target Schema's "data" field and put it in "source2"
- Use "" only if that specific cell doesn't exist in that table

Output Merged_Data in this EXACT structure:
{
  "Merged_Data": [
    {
      "Column_Name": {
        "VMD_data": [
          {
            "Row_Name": {
              "source1": "actual_value_from_table1",
              "source2": "actual_value_from_table2"
            }
          }
        ]
      }
    }
  ]
}

Example with real values:
If Source has: Bleeding column with Age row = "74.0±8.1"
If Target has: With vaccines column with Age row = "75.9±7.9"
Then output:
{
  "Bleeding.(n=35)": {
    "VMD_data": [
      {"Age, mean±SD,y": {"source1": "74.0±8.1", "source2": ""}}
    ]
  }
},
{
  "With vaccines.(n=48)": {
    "VMD_data": [
      {"Age, mean±SD,years": {"source1": "", "source2": "75.9±7.9"}}
    ]
  }
}

CRITICAL: ENGLISH ONLY OUTPUT
Ensure all text in the Merged_Data (values) and Merged_Schema (attributes) is in English. 
Translate if necessary.

Create mapping schemas:
{
  "HMD_Map_Schema1": [{"source1": "Merged_Schema.attr_name", "source2":"Schema1.attr_name"}],
  "VMD_Map_Schema1": [{"source1": "Merged_Schema.attr_name", "source2":"Schema1.attr_name"}],
  "HMD_Map_Schema2": [{"source1": "Merged_Schema.attr_name", "source2":"Schema2.attr_name"}],
  "VMD_Map_Schema2": [{"source1": "Merged_Schema.attr_name", "source2":"Schema2.attr_name"}],
}

If no valid matches exist, return: {"HMD_Merged_Schema":[], "VMD_Merged_Schema":[], "Merged_Data":[], "HMD_Map_Schema1":[], "VMD_Map_Schema1":[], "HMD_Map_Schema2":[], "VMD_Map_Schema2":[]}

VALIDATION CHECKLIST:
✓ Return ONLY valid JSON (no text outside JSON)
✓ Include all 7 required fields
✓ Merged_Data MUST contain actual cell values from the source tables, NOT empty strings
✓ Use proper JSON syntax
✓ Validate JSON before responding
            """
            },
            "kg_enhanced": {
                "match": """-----------------------------------------------------------
Knowledge Graph Enhanced Complex Match Operator - Input(schema1 and schema2)
                                                  - Output(map M)
-----------------------------------------------------------

Convert schema 1 (Table 1) and schema 2(Table 2) into JSON while preserving its structure.
Analyze the data nodes in the JSON for each schema and identify child attributes for each header attribute based on the hierarchical structure within the data node.
For each schema/table, list:
1) Horizontal (HMD) attributes along with their child attributes, if any.
2) Vertical (VMD) attributes along with their child attributes, if applicable.
3) Do not invent any attribute names unless they are present in the original schema.
For each schema/table, follow the JSON structure outlined below.

{
  "Table1.HMD": [
    {
      "attribute1": "Name",
      "children": [
        {
          "child_level1.attribute1": "name"
        },
        {
          "child_level1.attribute2": "name"
        }
        ]
    },
    {
      "attribute2": "Name",
      "children": [
        {
          "child_level1.attribute1": "name"
        },
        {
          "child_level1.attribute2": "name"
        }
        ]
    }
   ],
    "Table1.VMD":[
    {
      "attribute1": "name",
      "children": [
        {
          "child_level1.attribute1": "name"
        },
        {
          "child_level1.attribute2": "name"
        }]
    },
    {
      "attribute2": "name",
      "children": [
        {
          "child_level1.attribute1": "name"
        },
        {
          "child_level1.attribute2": "name"
        }]
    }
}

Given the HMD source schema and HMD target schema from above.

Act as an enhanced schema matcher for hierarchical, non-relational schemas with knowledge graph support.
Your task is to identify semantic matches between a source schema and a target schema by analyzing their nested JSON structure and leveraging external knowledge graphs for improved semantic understanding.

KNOWLEDGE GRAPH ENHANCEMENT:
Before performing matching, consider leveraging the following knowledge graphs and ontologies to understand semantic relationships:
1. DBpedia - For general domain knowledge and entity relationships
2. YAGO - For hierarchical taxonomies and semantic types
3. Wikidata - For structured data about entities and their properties
4. Schema.org - For web semantic markup and common data types
5. Domain-specific ontologies when applicable

For each attribute in both schemas:
- Look for synonyms, hypernyms, hyponyms, and related concepts
- Consider multilingual variations and alternative naming conventions
- Identify semantic type hierarchies (e.g., "age" and "years_old" both relate to temporal measurement)
- Use knowledge graph relationships to find indirect semantic connections

Each schema is represented as a hierarchical JSON, where:
Keys represent attribute hierarchy
Values specify attribute name
Nested structures ("children") define sub-attributes defined as child_level#, where # is number of levels
Two attributes semantically match if and only if there exists an invertible function that maps all values from one attribute (including its sub-attributes) to the corresponding target attribute, OR if they represent the same semantic concept according to knowledge graph relationships.

The set of all attribute names is called table schema or metadata. Metadata is a set of attributes of a table. Metadata can be stored in a row or in a column. A table with hierarchical metadata is a complex, non-relational table that, similar to a relational table, has metadata (i.e., attributes), but unlike a relational table it may be found not only in a row, but also in a column. It may also take several rows or columns. Such rows with metadata are called horizontal metadata (HMD).On the other hand, such columns with metadata are called vertical metadata (VMD)

Instructions:
I will first provide the source schema in a hierarchical JSON format.
Then, I will provide the target schema in the same format.
You must analyze the hierarchical relationships and identify semantic matches at all levels using knowledge graph insights when helpful.

Sample input JSON for a table (Table1 or Source) with separate JSON for HMD and VMD
{
  "Table1.HMD": [
    {
      "attribute1": "attribute1name"
    },
    {
      "attribute2": "attribute2name",
      "children": [
        {
          "child_level1attribute1": "child_level1attribute1name",
          "children": [
            {
              "child_level2attribute1": "child_level2attribute1name"
            }
          ]
        }
      ]
    }
  ]
}

{
  "Table1.VMD": [
    {
      "attribute1": "attribute1name"
    },
    {
      "attribute2": "attribute2name",
      "children": [
        {
          "child_level1attribute1": "child_level1attribute1name",
          "children": [
            {
              "child_level2attribute1": "child_level2attribute1name"
            }
          ]
        }
      ]
    }
  ]
}

Provide the output as a structured JSON, following the template
{
  {"HMD_matches": [
    {"source": "attribute1name", "target": "attribute1name"},
    {"source": "attribute2name", "target": ".attribute2name"},
    {"source": "attribute2name.child_level1attribute1name", "target":  "attribute2name.child_level1attribute1name"},
{"source": "attribute2name.child_level1attribute1name.child_level2attribute1name", "target": "attribute2name.child_level1attribute1name.child_level2attribute1name"}
  ]
  },
  {
  "VMD_matches": [
  {"source": "attribute1name", "target": "attribute1name"},
    {"source": "attribute2name", "target": ".attribute2name"},
    {"source": "attribute2name.child_level1attribute1name", "target":  "attribute2name.child_level1attribute1name"},
{"source": "attribute2name.child_level1attribute1name.child_level2attribute1name", "target": "attribute2name.child_level1attribute1name.child_level2attribute1name"}

  ]
}
}
If either HMD or VMD is not present return [] for respective keys.

Example Input (Source Schema):
{
  "Table1.HMD": [
    {
      "attribute1": "name"
    },
    {
      "attribute2": "birth_date",
      "children": [
        {
          "child_level1.attribute1": "date_of_birth",
          "children": [
            {
              "child_level2.attribute1": "dob_formatted"
            }
          ]
        }
      ]
    }
  ]
}

Example Input (Target Schema):

{
  "Table2.HMD": [
    {
      "attribute1": "full_name"
    },
    {
      "attribute2": "dob",
      "children": [
        {
          "child_level1.attribute1": "dob_field",
          "children": [
            {
              "child_level2.attribute1": "formatted_dob"
            }
          ]
        }
      ]
    }
  ]
}

Expected Output (Schema Matches):
{
  {
   "HMD_matches": [
    {"source": "name", "target": "full_name"},
    {"source": "birth_date", "target": "dob"},
    {"source": "birth_date.date_of_birth", "target": "dob.dob_field"},
    {"source": "birth_date.date_of_birth.dob_formatted", "target": "dob.dob_field.formatted_dob"}
  ]
  },
  {
  "VMD_matches": []
}
}""",
                "merge": """Given are Table 1 (source1) and Table 2 (source2) in the [document or json file].

Convert schema 1 (Table 1) and schema 2(Table 2) into JSON while preserving its structure.
Analyze the data nodes in the JSON for each schema and identify child attributes for each header attribute based on the hierarchical structure within the data node.
For each schema/table, list:
1) Horizontal (HMD) attributes along with their child attributes, if any.
2) Vertical (VMD) attributes along with their child attributes, if applicable.
3) Do not invent any attribute names unless they are present in the original schema.
For each schema/table, follow the JSON structure outlined below.

{
  "Table1.HMD": [
    {
      "attribute1": "Name",
      "children": [
        {
          "child_level1.attribute1": "name"
        },
        {
          "child_level1.attribute2": "name"
        }
        ]
    },
    {
      "attribute2": "Name",
      "children": [
        {
          "child_level1.attribute1": "name"
        },
        {
          "child_level1.attribute2": "name"
        }
        ]
    }
   ],
    "Table1.VMD":[
    {
      "attribute1": "name",
      "children": [
        {
          "child_level1.attribute1": "name"
        },
        {
          "child_level1.attribute2": "name"
        }]
    },
    {
      "attribute2": "name",
      "children": [
        {
          "child_level1.attribute1": "name"
        },
        {
          "child_level1.attribute2": "name"
        }]
    }
}

Given the HMD source1 schema and HMD target/source2 schema from above.


Act as a schema merger for hierarchical, non-relational schemas.
Your task is to merge the attributes that are matched between the source1 (Table 1) and a source2 (Table 2) using the following match results:

Match Results:
{match_results_placeholder}

Source Schema:
{source_schema_placeholder}

Target Schema:
{target_schema_placeholder}


Create a new merged schema (Merged_Schema) from the matched attributes above.
Add all remaining HDM and VMD attributes and their children from source1 (Schema1/Table1) and source2 (Schema2/Table2) in the new merged schema (Merged_Schema).
Output them in JSON format in the following structure:

{
  "HMD_Merged_Schema": ["attr_name", "attr_name.child_attr_name"],
  "VMD_Merged_Schema": ["attr_name", "attr_name.child_attr_name"],
}

Using the merged schema (Merged_Schema), for each HMD attribute in the HMD_Merged_Schema,
go through all the VMD attributes in the VMD_Merged_Schema list and add the corresponding values from source and target tables.
If no values are available, add "".
If HMD attribute has children then skip the attribute and create a list only for the children.
Output them in JSON format in the following structure:
}
"Merged_Data":[
        {"HMD.attr_name.child_name": "value" {
                {"VMD.attr_name.child_name1","source1": "value", "source2":"value"},
                {"VMD.attr_name.child_name2","source1": "value", "source2":"value"}
        }
        ]
}

Create a new map schema (Map_Schema1) that includes only the source1 (Schema1/Table1) attributes contained in the matches mapping.
Output them in JSON format in the following structure:

{
  "HMD_Map_Schema1": [{"source1": "Merged_Schema.attr_name", "source2":"Schema1.attr_name"}],
  "VMD_Map_Schema1": [{"source1": "Merged_Schema.attr_name", "source2":"Schema1.attr_name"}],
}

Create a new map schema (Map_Schema2) that includes only the source2 (Schema2/Table2) attributes contained in the matches mapping.
Output them in JSON format in the following structure:
{
  "HMD_Map_Schema2": [{"source1": "Merged_Schema.attr_name", "source2":"Schema2.attr_name"}],
  "VMD_Map_Schema2": [{"source1": "Merged_Schema.attr_name", "source2":"Schema2.attr_name"}],
}


If no valid matches exist, return: {"Merged_Schema":[]}""",
                "instance_merge": """Given are Table 1 (source1) and Table 2 (source2) in the [document or json file].

Convert schema 1 (Table 1) and schema 2(Table 2) into JSON while preserving its structure.
Analyze the data nodes in the JSON for each schema and identify child attributes for each header attribute based on the hierarchical structure within the data node.
For each schema/table, list:
1) Horizontal (HMD) attributes along with their child attributes, if any.
2) Vertical (VMD) attributes along with their child attributes, if applicable.
3) Do not invent any attribute names unless they are present in the original schema.
For each schema/table, follow the JSON structure outlined below.

{
  "Table1.HMD": [
    {
      "attribute1": "Name",
      "children": [
        {
          "child_level1.attribute1": "name"
        },
        {
          "child_level1.attribute2": "name"
        }
        ]
    },
    {
      "attribute2": "Name",
      "children": [
        {
          "child_level1.attribute1": "name"
        },
        {
          "child_level1.attribute2": "name"
        }
        ]
    }
   ],
    "Table1.VMD":[
    {
      "attribute1": "name",
      "children": [
        {
          "child_level1.attribute1": "name"
        },
        {
          "child_level1.attribute2": "name"
        }]
    },
    {
      "attribute2": "name",
      "children": [
        {
          "child_level1.attribute1": "name"
        },
        {
          "child_level1.attribute2": "name"
        }]
    }
}

Given the HMD source1 schema and HMD target/source2 schema from above.


Act as a schema merger for hierarchical, non-relational schemas.
Your task is to merge the attributes that are matched between the source1 (Table 1) and a source2 (Table 2) using the following match results:

Match Results:
{match_results_placeholder}

Source Schema:
{source_schema_placeholder}

Target Schema:
{target_schema_placeholder}


Create a new merged schema (Merged_Schema) from the matched attributes above.
Add all remaining HDM and VMD attributes and their children from source1 (Schema1/Table1) and source2 (Schema2/Table2) in the new merged schema (Merged_Schema).
Output them in JSON format in the following structure:

{
  "HMD_Merged_Schema": ["attr_name", "attr_name.child_attr_name"],
  "VMD_Merged_Schema": ["attr_name", "attr_name.child_attr_name"],
}

Using the merged schema (Merged_Schema), for each HMD attribute in the HMD_Merged_Schema,
go through all the VMD attributes in the VMD_Merged_Schema list and add the corresponding values from source and target tables.
If no values are available, add "".
If HMD attribute has children then skip the attribute and create a list only for the children.
Output them in JSON format in the following structure:
}
"Merged_Data":[
        {"HMD.attr_name.child_name": "value" {
                {"VMD.attr_name.child_name1","source1": "value", "source2":"value"},
                {"VMD.attr_name.child_name2","source1": "value", "source2":"value"}
        }
        ]
}

Create a new map schema (Map_Schema1) that includes only the source1 (Schema1/Table1) attributes contained in the matches mapping.
Output them in JSON format in the following structure:

{
  "HMD_Map_Schema1": [{"source": "Merged_Schema.attr_name", "target":"Schema1.attr_name"}],
  "VMD_Map_Schema1": [{"source": "Merged_Schema.attr_name", "target":"Schema1.attr_name"}],
}

Create a new map schema (Map_Schema2) that includes only the source2 (Schema2/Table2) attributes contained in the matches mapping.
Output them in JSON format in the following structure:

{ "HMD_Map_Schema2": [{"source": "Merged_Schema.attr_name", "target":"Schema2.attr_name"}],
  "VMD_Map_Schema2": [{"source": "Merged_Schema.attr_name", "target":"Schema2.attr_name"}],
}

If no valid matches exist, return: {"HMD_Merged_Schema":[], "VMD_Merged_Schema":[], "Merged_Data":{}, "HMD_Map_Schema1":[], "VMD_Map_Schema1":[], "HMD_Map_Schema2":[], "VMD_Map_Schema2":[]}

VALIDATION CHECKLIST:
✓ Return ONLY valid JSON (no text outside JSON)
✓ Include all 7 required fields: HMD_Merged_Schema, VMD_Merged_Schema, Merged_Data, HMD_Map_Schema1, VMD_Map_Schema1, HMD_Map_Schema2, VMD_Map_Schema2
✓ Use proper JSON syntax (commas, brackets, quotes)
✓ Validate JSON before responding
            """
            },
            "multi_step": {
                "match": """-----------------------------------------------------------
Multi-Step Complex Match Operator - Input(schema1 and schema2)
                                   - Output(map M)
                         Using 3-Round Ensemble Approach
-----------------------------------------------------------

Convert schema 1 (Table 1) and schema 2(Table 2) into JSON while preserving its structure.
Analyze the data nodes in the JSON for each schema and identify child attributes for each header attribute based on the hierarchical structure within the data node.
For each schema/table, list:
1) Horizontal (HMD) attributes along with their child attributes, if any.
2) Vertical (VMD) attributes along with their child attributes, if applicable.
3) Do not invent any attribute names unless they are present in the original schema.
For each schema/table, follow the JSON structure outlined below.

{
  "Table1.HMD": [
    {
      "attribute1": "Name",
      "children": [
        {
          "child_level1.attribute1": "name"
        },
        {
          "child_level1.attribute2": "name"
        }
        ]
    },
    {
      "attribute2": "Name",
      "children": [
        {
          "child_level1.attribute1": "name"
        },
        {
          "child_level1.attribute2": "name"
        }
        ]
    }
   ],
    "Table1.VMD":[
    {
      "attribute1": "name",
      "children": [
        {
          "child_level1.attribute1": "name"
        },
        {
          "child_level1.attribute2": "name"
        }]
    },
    {
      "attribute2": "name",
      "children": [
        {
          "child_level1.attribute1": "name"
        },
        {
          "child_level1.attribute2": "name"
        }]
    }
}

Given the HMD source schema and HMD target schema from above.

Act as a schema matcher for hierarchical, non-relational schemas.
Your task is to identify semantic matches between a source schema and a target schema by analyzing their nested JSON structure.

MULTI-STEP APPROACH INSTRUCTIONS:
- This is one of three independent matching attempts
- Use your best judgment and reasoning for this specific attempt
- Consider different semantic perspectives and matching strategies
- Focus on finding accurate and meaningful matches
- Be thorough in your analysis

Each schema is represented as a hierarchical JSON, where:
Keys represent attribute hierarchy
Values specify attribute name
Nested structures ("children") define sub-attributes defined as child_level#, where # is number of levels
Two attributes semantically match if and only if there exists an invertible function that maps all values from one attribute (including its sub-attributes) to the corresponding target attribute.

The set of all attribute names is called table schema or metadata. Metadata is a set of attributes of a table. Metadata can be stored in a row or in a column. A table with hierarchical metadata is a complex, non-relational table that, similar to a relational table, has metadata (i.e., attributes), but unlike a relational table it may be found not only in a row, but also in a column. It may also take several rows or columns. Such rows with metadata are called horizontal metadata (HMD).On the other hand, such columns with metadata are called vertical metadata (VMD)

Instructions:
I will first provide the source schema in a hierarchical JSON format.
Then, I will provide the target schema in the same format.
You must analyze the hierarchical relationships and identify semantic matches at all levels.

Sample input JSON for a table (Table1 or Source) with separate JSON for HMD and VMD
{
  "Table1.HMD": [
    {
      "attribute1": "attribute1name"
    },
    {
      "attribute2": "attribute2name",
      "children": [
        {
          "child_level1attribute1": "child_level1attribute1name",
          "children": [
            {
              "child_level2attribute1": "child_level2attribute1name"
            }
          ]
        }
      ]
    }
  ]
}

{
  "Table1.VMD": [
    {
      "attribute1": "attribute1name"
    },
    {
      "attribute2": "attribute2name",
      "children": [
        {
          "child_level1attribute1": "child_level1attribute1name",
          "children": [
            {
              "child_level2attribute1": "child_level2attribute1name"
            }
          ]
        }
      ]
    }
  ]
}

Provide the output as a structured JSON, following the template
{
  {"HMD_matches": [
    {"source": "attribute1name", "target": "attribute1name"},
    {"source": "attribute2name", "target": ".attribute2name"},
    {"source": "attribute2name.child_level1attribute1name", "target":  "attribute2name.child_level1attribute1name"},
{"source": "attribute2name.child_level1attribute1name.child_level2attribute1name", "target": "attribute2name.child_level1attribute1name.child_level2attribute1name"}
  ]
  },
  {
  "VMD_matches": [
  {"source": "attribute1name", "target": "attribute1name"},
    {"source": "attribute2name", "target": ".attribute2name"},
    {"source": "attribute2name.child_level1attribute1name", "target":  "attribute2name.child_level1attribute1name"},
{"source": "attribute2name.child_level1attribute1name.child_level2attribute1name", "target": "attribute2name.child_level1attribute1name.child_level2attribute1name"}

  ]
}
}
If either HMD or VMD is not present return [] for respective keys.""",

                "merge": """Given are the following schemas and their match results:

Source Schema:
{source_schema_placeholder}

Target Schema:
{target_schema_placeholder}

Match Results:
{match_results_placeholder}

Act as a schema merger for hierarchical, non-relational schemas.
Your task is to merge the attributes that are matched between the source1 (Table 1) and a source2 (Table 2) using the match results provided above.

MULTI-STEP APPROACH INSTRUCTIONS:
- This is one of three independent merging attempts
- Use your best judgment for this specific merge attempt
- Consider different merging strategies and perspectives
- Focus on creating a comprehensive and accurate merged schema

Create a new merged schema (Merged_Schema) from the matched attributes above.
Add all remaining HDM and VMD attributes and their children from source1 (Schema1/Table1) and source2 (Schema2/Table2) in the new merged schema (Merged_Schema).
Output them in JSON format in the following structure:

{
  "HMD_Merged_Schema": ["attr_name", "attr_name.child_attr_name"],
  "VMD_Merged_Schema": ["attr_name", "attr_name.child_attr_name"],
}

Using the merged schema (Merged_Schema), for each HMD attribute in the HMD_Merged_Schema,
go through all the VMD attributes in the VMD_Merged_Schema list and add the corresponding values from source and target tables.
If no values are available, add "".
If HMD attribute has children then skip the attribute and create a list only for the children.
Output them in JSON format in the following structure:
}
"Merged_Data":[
        {"HMD.attr_name.child_name": "value" {
                {"VMD.attr_name.child_name1","source1": "value", "source2":"value"},
                {"VMD.attr_name.child_name2","source1": "value", "source2":"value"}
        }
        ]
}

Create a new map schema (Map_Schema1) that includes only the source1 (Schema1/Table1) attributes contained in the matches mapping.
Output them in JSON format in the following structure:

{
  "HMD_Map_Schema1": [{"source1": "Merged_Schema.attr_name", "source2":"Schema1.attr_name"}],
  "VMD_Map_Schema1": [{"source1": "Merged_Schema.attr_name", "source2":"Schema1.attr_name"}],
}

Create a new map schema (Map_Schema2) that includes only the source2 (Schema2/Table2) attributes contained in the matches mapping.
Output them in JSON format in the following structure:
{
  "HMD_Map_Schema2": [{"source1": "Merged_Schema.attr_name", "source2":"Schema2.attr_name"}],
  "VMD_Map_Schema2": [{"source1": "Merged_Schema.attr_name", "source2":"Schema2.attr_name"}],
}

If no valid matches exist, return: {"Merged_Schema":[]}""",

                "instance_merge": """Given are the following schemas and their match results:

Source Schema:
{source_schema_placeholder}

Target Schema:
{target_schema_placeholder}

Match Results:
{match_results_placeholder}

Act as a schema merger for hierarchical, non-relational schemas.
Your task is to merge the attributes that are matched between the source1 (Table 1) and a source2 (Table 2) using the match results provided above.

MULTI-STEP APPROACH INSTRUCTIONS:
- This is one of three independent instance merging attempts
- Use your best judgment for this specific instance merge attempt
- Consider different instance merging strategies and perspectives
- Focus on creating accurate merged data instances

Create a new merged schema (Merged_Schema) from the matched attributes above.
Add all remaining HDM and VMD attributes and their children from source1 (Schema1/Table1) and source2 (Schema2/Table2) in the new merged schema (Merged_Schema).
Output them in JSON format in the following structure:

{
  "HMD_Merged_Schema": ["attr_name", "attr_name.child_attr_name"],
  "VMD_Merged_Schema": ["attr_name", "attr_name.child_attr_name"],
}

Using the merged schema (Merged_Schema), for each HMD attribute in the HMD_Merged_Schema,
go through all the VMD attributes in the VMD_Merged_Schema list and add the corresponding values from source and target tables.
If no values are available, add "".
If HMD attribute has children then skip the attribute and create a list only for the children.
Output them in JSON format in the following structure:
}
"Merged_Data":[
        {"HMD.attr_name.child_name": "value" {
                {"VMD.attr_name.child_name1","source1": "value", "source2":"value"},
                {"VMD.attr_name.child_name2","source1": "value", "source2":"value"}
        }
        ]
}

Create a new map schema (Map_Schema1) that includes only the source1 (Schema1/Table1) attributes contained in the matches mapping.
Output them in JSON format in the following structure:

{
  "HMD_Map_Schema1": [{"source": "Merged_Schema.attr_name", "target":"Schema1.attr_name"}],
  "VMD_Map_Schema1": [{"source": "Merged_Schema.attr_name", "target":"Schema1.attr_name"}],
}

Create a new map schema (Map_Schema2) that includes only the source2 (Schema2/Table2) attributes contained in the matches mapping.
Output them in JSON format in the following structure:

{ "HMD_Map_Schema2": [{"source": "Merged_Schema.attr_name", "target":"Schema2.attr_name"}],
  "VMD_Map_Schema2": [{"source": "Merged_Schema.attr_name", "target":"Schema2.attr_name"}],
}

If no valid matches exist, return: {"HMD_Merged_Schema":[], "VMD_Merged_Schema":[], "Merged_Data":{}, "HMD_Map_Schema1":[], "VMD_Map_Schema1":[], "HMD_Map_Schema2":[], "VMD_Map_Schema2":[]}

VALIDATION CHECKLIST:
✓ Return ONLY valid JSON (no text outside JSON)
✓ Include all 7 required fields: HMD_Merged_Schema, VMD_Merged_Schema, Merged_Data, HMD_Map_Schema1, VMD_Map_Schema1, HMD_Map_Schema2, VMD_Map_Schema2
✓ Use proper JSON syntax (commas, brackets, quotes)
✓ Validate JSON before responding
            """,

                "ensemble": """You are an ensemble aggregator for multi-step schema processing results.

You have been given 3 independent responses for the same schema operation. Your task is to analyze these responses and create a single, high-quality merged result that combines the best aspects of all three responses.

ENSEMBLE AGGREGATION INSTRUCTIONS:
1. Compare the three responses carefully
2. Look for consensus across responses - matches/mappings that appear in multiple responses are likely correct
3. Use majority voting where applicable
4. For merge operations, combine unique valid entries from all responses
5. Maintain the exact same JSON structure as the individual responses
6. Ensure completeness - don't lose valid information from any response
7. Prioritize quality and accuracy over quantity

INPUT: Three independent responses labeled Response1, Response2, and Response3

Response1:
{response1}

Response2:
{response2}

Response3:
{response3}

OUTPUT: A single aggregated response following the exact same JSON structure as the input responses.

For matching operations, output:
{
  "HMD_matches": [...],
  "VMD_matches": [...]
}

For merge/instance_merge operations, output:
{
  "HMD_Merged_Schema": [...],
  "VMD_Merged_Schema": [...],
  "Merged_Data": [...],
  "HMD_Map_Schema1": [...],
  "VMD_Map_Schema1": [...],
  "HMD_Map_Schema2": [...],
  "VMD_Map_Schema2": [...]
}

Apply ensemble logic to create the best possible aggregated result."""
            }
        },
        "schema": {
            "json_default": {
                "merge": """Given are sources (Schema1/Table1) and target (Schema2/Table2) in the [document or json file].

Act as a schema merger for hierarchical, non-relational schemas.
Your task is to merge the attributes that are matched between the source schema (Table1) and a target schema (Table2) using the following match results:

Match Results:
{match_results_placeholder}

Source Schema:
{source_schema_placeholder}

Target Schema:
{target_schema_placeholder}

Create a new merged schema from the matched attributes above.
Add all remaining HMD and VMD attributes and their children from source1 (Schema1/Table1) and source2 (Schema2/Table2) in the new merged schema (Merged_Schema).
Output them in JSON format in the following structure:

{
  "HMD_Merged_Schema": ["attr_name", "attr_name.child_attr_name"],
  "VMD_Merged_Schema": ["attr_name", "attr_name.child_attr_name"],
  "Merged_Data": [...],
  "HMD_Map_Schema1": [...],
  "VMD_Map_Schema1": [...],
  "HMD_Map_Schema2": [...],
  "VMD_Map_Schema2": [...]
}

If no valid matches exist, return: {"Merged_Schema":[]}"""
            },
            "multi_step": {
                "merge": """Given are the following schemas and their match results:

Source Schema:
{source_schema_placeholder}

Target Schema:
{target_schema_placeholder}

Match Results:
{match_results_placeholder}

MULTI-STEP SCHEMA MERGE INSTRUCTIONS:
- This is one of three independent schema merging attempts
- Use your best judgment for this specific schema merge attempt
- Consider different merging strategies and perspectives
- Focus on creating accurate merged schema structures

Act as a schema merger for hierarchical, non-relational schemas.
Your task is to merge the attributes that are matched between the source1 (Table 1) and a source2 (Table 2) using the match results provided above.

Create a new merged schema from the matched attributes above.
Add all remaining HMD and VMD attributes and their children from source1 (Schema1/Table1) and source2 (Schema2/Table2) in the new merged schema (Merged_Schema).
Output them in JSON format in the following structure:

{
  "HMD_Merged_Schema": ["attr_name", "attr_name.child_attr_name"],
  "VMD_Merged_Schema": ["attr_name", "attr_name.child_attr_name"],
  "Merged_Data": [...],
  "HMD_Map_Schema1": [...],
  "VMD_Map_Schema1": [...],
  "HMD_Map_Schema2": [...],
  "VMD_Map_Schema2": [...]
}

If no valid matches exist, return: {"Merged_Schema":[]}"""
            }
        },
        "instance": {
            "json_default": {
                "merge": """Given are sources (Schema1/Table1) and target (Schema2/Table2) in the [document or json file].

Act as an instance merger for hierarchical, non-relational schemas.
Your task is to merge the actual data instances that are matched between the source schema (Table1) and a target schema (Table2) using the following match results:

Match Results:
{match_results_placeholder}

Source Schema:
{source_schema_placeholder}

Target Schema:
{target_schema_placeholder}

Create a new merged schema from the matched attributes above and merge the actual data instances.
Focus on combining the data values from both schemas, not just the structure.
Output them in JSON format in the following structure:

{
  "HMD_Merged_Schema": ["attr_name", "attr_name.child_attr_name"],
  "VMD_Merged_Schema": ["attr_name", "attr_name.child_attr_name"],
  "Merged_Data": [...],
  "HMD_Map_Schema1": [...],
  "VMD_Map_Schema1": [...],
  "HMD_Map_Schema2": [...],
  "VMD_Map_Schema2": [...]
}

If no valid matches exist, return: {"Merged_Schema":[]}"""
            }
        }
    },
    "relational": {
        "baseline": {
            "json_default": {
                "match": """Given are Schema1/Table 1 (source) and Schema2/Table 2 (target) in the [document, json file or images].
Identify the header attributes for the source and target schemas/tables.
Match the similar attributes between the source and target schemas/tables and output the matches in JSON structure:

{
 "matches": [{"source": "attribute_name1", "target": "attribute_name3"}]
}""",
                "merge": """Given are Schema1/Table 1 (source) and Schema2/Table 2 (target) in the [document, json file or images].
Identify the header attributes for the source and target schemas/tables.
Given are the following schemas and their match results:
Source Schema:
{source_schema_placeholder}
Target Schema:
{target_schema_placeholder}
Match Results:
{match_results_placeholder}
Act as a schema merger for hierarchical, non-relational schemas.
Your task is to merge the attributes that are matched between the source1 (Table 1) and a source2 (Table 2) using the match results provided above.

Create a new merged schema (Merged_Schema) from the matched attributes above.
Ensure the merged table includes all matching attributes and values from both source and target schemas.
Output the result in JSON format with the following structure:
{
  "HMD_Merged_Schema": [],
  "VMD_Merged_Schema": [],
  "Merged_Schema": [],
  "Merged_Data": []
}"""
            }
        },
        "operator": {
            "json_default": {
                "match": """Given are Table 1 (source) and Table 2 (target) in the [document or json file].
Analyze the tables and identify the header attributes for the source and target tables.

Act as a schema matcher for relational schemas.
Your task is to identify semantic matches between header attributes in a source schema (Table1) and a target schema (Table2) based on strict invertible transformations.
Two header attributes semantically match if and only if there exists an invertible function that maps all values of one attribute to the corresponding values of the other.

Instructions:
I will first input the header attribute names from the source schema.
Then, I will input the header attribute names from the target schema.
You must determine semantic matches between the source and target attributes.
Provide the output in JSON format as a mapping of matched attributes in the following structure:

{
"matches": [
{"source": "Table1.attr_name", "target": "Table2.attr_name"},
{"source": "Table1.attr_name", "target": "Table2.attr_name"}
]
}

If no valid matches exist, return: {"matches": []}""",
                "merge": """Given are sources (Schema1/Table1) and target (Schema2/Table2) in the [document or json file].
Analyze the tables and identify the header attributes for the source and target tables.

Act as a schema merger for relational schemas.
Your task is to merge the attributes that are matched between the source schema (Table1) and a target schema (Table2) using the following match results:

Match Results:
{match_results_placeholder}

Source Schema:
{source_schema_placeholder}

Target Schema:
{target_schema_placeholder}

Create a new merged schema from the matched attributes above and all remaining attributes in source (Schema1/Table1) and target (Schema2/Table2).
Add the attribute values in the "Merged_Data" and if no values are available, add "".
If the matched attributes from source and target have similar or the same valules, add source value and target value.
Also add the non-matched rows from both source and target tables.
Output them in JSON format in the following structure:

{ "Merged_Schema": ["attr_name", "attr_name"], "Merged_Data":["attr_name.value", { "source": "attr_name.value", "target":"attr_name.value"}] }

Create a new map schema (Map_Schema1) that includes only the source (Schema1/Table1) attributes contained in the matches mapping.
Output them in JSON format in the following structure:

{ "Map_Schema1": [ {"source": "Merged_Schema.attr_name", "target":"Schema1.attr_name"}]}

Create a new map schema (Map_Schema2) that includes only the target (Schema2/Table2) attributes contained in the matches mapping.
Output them in JSON format in the following structure:

{ "Map_Schema2": [ {"source": "Merged_Schema.attr_name", "target":"Schema2.attr_name"}]}

If no valid matches exist, return: {"Merged_Schema":[]}""",
                "instance_merge": """Given are sources (Schema1/Table1) and target (Schema2/Table2) in the [document or json file].
Analyze the tables and identify the header attributes for the source and target tables.

Act as a schema merger for relational schemas.
Your task is to merge the attributes that are matched between the source schema (Table1) and a target schema (Table2) using the following match results:

Match Results:
{match_results_placeholder}

Source Schema:
{source_schema_placeholder}

Target Schema:
{target_schema_placeholder}

Create a new merged schema from the matched attributes above and all remaining attributes in source (Schema1/Table1) and target (Schema2/Table2).
Add the attribute values in the "Merged_Data" and if no values are available, add "".
If the matched attributes from source and target have similar or the same valules, add source value and target value.
Also add the non-matched rows from both source and target tables.
Output them in JSON format in the following structure:

{ "Merged_Schema": ["attr_name", "attr_name"], "Merged_Data":["attr_name.value", { "source": "attr_name.value", "target":"attr_name.value"}] }

Create a new map schema (Map_Schema1) that includes only the source (Schema1/Table1) attributes contained in the matches mapping.
Output them in JSON format in the following structure:

{ "Map_Schema1": [ {"source": "Merged_Schema.attr_name", "target":"Schema1.attr_name"}]}

Create a new map schema (Map_Schema2) that includes only the target (Schema2/Table2) attributes contained in the matches mapping.
Output them in JSON format in the following structure:

{ "Map_Schema2": [ {"source": "Merged_Schema.attr_name", "target":"Schema2.attr_name"}]}

If no valid matches exist, return: {"Merged_Schema":[]}"""
            },
            "kg_enhanced": {
                "match": """Given are Table 1 (source) and Table 2 (target) in the [document or json file].
Analyze the tables and identify the header attributes for the source and target tables.

Act as an enhanced schema matcher for relational schemas with knowledge graph support.
Your task is to identify semantic matches between header attributes in a source schema (Table1) and a target schema (Table2) based on strict invertible transformations and enhanced by knowledge graph relationships.

KNOWLEDGE GRAPH ENHANCEMENT:
Before performing matching, consider leveraging the following knowledge graphs and ontologies to understand semantic relationships:
1. DBpedia - For general domain knowledge and entity relationships
2. YAGO - For hierarchical taxonomies and semantic types
3. Wikidata - For structured data about entities and their properties
4. Schema.org - For web semantic markup and common data types
5. Domain-specific ontologies when applicable

For each attribute in both schemas:
- Look for synonyms, hypernyms, hyponyms, and related concepts
- Consider multilingual variations and alternative naming conventions
- Identify semantic type hierarchies (e.g., "age" and "years_old" both relate to temporal measurement)
- Use knowledge graph relationships to find indirect semantic connections

Two header attributes semantically match if and only if there exists an invertible function that maps all values of one attribute to the corresponding values of the other, OR if they represent the same semantic concept according to knowledge graph relationships.

Instructions:
I will first input the header attribute names from the source schema.
Then, I will input the header attribute names from the target schema.
You must determine semantic matches between the source and target attributes using knowledge graph insights when helpful.
Provide the output in JSON format as a mapping of matched attributes in the following structure:

{
"matches": [
{"source": "Table1.attr_name", "target": "Table2.attr_name"},
{"source": "Table1.attr_name", "target": "Table2.attr_name"}
]
}

If no valid matches exist, return: {"matches": []}""",
                "merge": """Given are sources (Schema1/Table1) and target (Schema2/Table2) in the [document or json file].
Analyze the tables and identify the header attributes for the source and target tables.

Act as a schema merger for relational schemas.
Your task is to merge the attributes that are matched between the source schema (Table1) and a target schema (Table2) using the following match results:

Match Results:
{match_results_placeholder}

Source Schema:
{source_schema_placeholder}

Target Schema:
{target_schema_placeholder}

Create a new merged schema from the matched attributes above and all remaining attributes in source (Schema1/Table1) and target (Schema2/Table2).
Add the attribute values in the "Merged_Data" and if no values are available, add "".
If the matched attributes from source and target have similar or the same valules, add source value and target value.
Also add the non-matched rows from both source and target tables.
Output them in JSON format in the following structure:

{ "Merged_Schema": ["attr_name", "attr_name"], "Merged_Data":["attr_name.value", { "source": "attr_name.value", "target":"attr_name.value"}] }

Create a new map schema (Map_Schema1) that includes only the source (Schema1/Table1) attributes contained in the matches mapping.
Output them in JSON format in the following structure:

{ "Map_Schema1": [ {"source": "Merged_Schema.attr_name", "target":"Schema1.attr_name"}]}

Create a new map schema (Map_Schema2) that includes only the target (Schema2/Table2) attributes contained in the matches mapping.
Output them in JSON format in the following structure:

{ "Map_Schema2": [ {"source": "Merged_Schema.attr_name", "target":"Schema2.attr_name"}]}

If no valid matches exist, return: {"Merged_Schema":[]}""",
                "instance_merge": """Given are sources (Schema1/Table1) and target (Schema2/Table2) in the [document or json file].
Analyze the tables and identify the header attributes for the source and target tables.

Act as a schema merger for relational schemas.
Your task is to merge the attributes that are matched between the source schema (Table1) and a target schema (Table2) using the following match results:

Match Results:
{match_results_placeholder}

Source Schema:
{source_schema_placeholder}

Target Schema:
{target_schema_placeholder}

Create a new merged schema from the matched attributes above and all remaining attributes in source (Schema1/Table1) and target (Schema2/Table2).
Add the attribute values in the "Merged_Data" and if no values are available, add "".
If the matched attributes from source and target have similar or the same valules, add source value and target value.
Also add the non-matched rows from both source and target tables.
Output them in JSON format in the following structure:

{ "Merged_Schema": ["attr_name", "attr_name"], "Merged_Data":["attr_name.value", { "source": "attr_name.value", "target":"attr_name.value"}] }

Create a new map schema (Map_Schema1) that includes only the source (Schema1/Table1) attributes contained in the matches mapping.
Output them in JSON format in the following structure:

{ "Map_Schema1": [ {"source": "Merged_Schema.attr_name", "target":"Schema1.attr_name"}]}

Create a new map schema (Map_Schema2) that includes only the target (Schema2/Table2) attributes contained in the matches mapping.
Output them in JSON format in the following structure:

{ "Map_Schema2": [ {"source": "Merged_Schema.attr_name", "target":"Schema2.attr_name"}]}

If no valid matches exist, return: {"Merged_Schema":[]}"""
            },
            "multi_step": {
                "match": """Given are Table 1 (source) and Table 2 (target) in the [document or json file].
Analyze the tables and identify the header attributes for the source and target tables.

Act as a schema matcher for relational schemas.
Your task is to identify semantic matches between header attributes in a source schema (Table1) and a target schema (Table2) based on strict invertible transformations.

MULTI-STEP APPROACH INSTRUCTIONS:
- This is one of three independent matching attempts
- Use your best judgment and reasoning for this specific attempt
- Consider different semantic perspectives and matching strategies
- Focus on finding accurate and meaningful matches
- Be thorough in your analysis

Two header attributes semantically match if and only if there exists an invertible function that maps all values of one attribute to the corresponding values of the other.

Instructions:
I will first input the header attribute names from the source schema.
Then, I will input the header attribute names from the target schema.
You must determine semantic matches between the source and target attributes.
Provide the output in JSON format as a mapping of matched attributes in the following structure:

{
"matches": [
{"source": "Table1.attr_name", "target": "Table2.attr_name"},
{"source": "Table1.attr_name", "target": "Table2.attr_name"}
]
}

If no valid matches exist, return: {"matches": []}""",
                "merge": """Given are sources (Schema1/Table1) and target (Schema2/Table2) in the [document or json file].
Analyze the tables and identify the header attributes for the source and target tables.

Act as a schema merger for relational schemas.
Your task is to merge the attributes that are matched between the source schema (Table1) and a target schema (Table2) using the following match results:

MULTI-STEP APPROACH INSTRUCTIONS:
- This is one of three independent merging attempts
- Use your best judgment for this specific merge attempt
- Consider different merging strategies and perspectives
- Focus on creating a comprehensive and accurate merged schema

Match Results:
{match_results_placeholder}

Source Schema:
{source_schema_placeholder}

Target Schema:
{target_schema_placeholder}

Create a new merged schema from the matched attributes above and all remaining attributes in source (Schema1/Table1) and target (Schema2/Table2).
Add the attribute values in the "Merged_Data" and if no values are available, add "".
If the matched attributes from source and target have similar or the same valules, add source value and target value.
Also add the non-matched rows from both source and target tables.
Output them in JSON format in the following structure:

{ "Merged_Schema": ["attr_name", "attr_name"], "Merged_Data":["attr_name.value", { "source": "attr_name.value", "target":"attr_name.value"}] }

Create a new map schema (Map_Schema1) that includes only the source (Schema1/Table1) attributes contained in the matches mapping.
Output them in JSON format in the following structure:

{ "Map_Schema1": [ {"source": "Merged_Schema.attr_name", "target":"Schema1.attr_name"}]}

Create a new map schema (Map_Schema2) that includes only the target (Schema2/Table2) attributes contained in the matches mapping.
Output them in JSON format in the following structure:

{ "Map_Schema2": [ {"source": "Merged_Schema.attr_name", "target":"Schema2.attr_name"}]}

If no valid matches exist, return: {"Merged_Schema":[]}""",
                "instance_merge": """Given are sources (Schema1/Table1) and target (Schema2/Table2) in the [document or json file].
Analyze the tables and identify the header attributes for the source and target tables.

Act as a schema merger for relational schemas.
Your task is to merge the attributes that are matched between the source schema (Table1) and a target schema (Table2) using the following match results:

MULTI-STEP APPROACH INSTRUCTIONS:
- This is one of three independent instance merging attempts
- Use your best judgment for this specific instance merge attempt
- Consider different instance merging strategies and perspectives
- Focus on creating accurate merged data instances

Match Results:
{match_results_placeholder}

Source Schema:
{source_schema_placeholder}

Target Schema:
{target_schema_placeholder}

Create a new merged schema from the matched attributes above and all remaining attributes in source (Schema1/Table1) and target (Schema2/Table2).
Add the attribute values in the "Merged_Data" and if no values are available, add "".
If the matched attributes from source and target have similar or the same valules, add source value and target value.
Also add the non-matched rows from both source and target tables.
Output them in JSON format in the following structure:

{ "Merged_Schema": ["attr_name", "attr_name"], "Merged_Data":["attr_name.value", { "source": "attr_name.value", "target":"attr_name.value"}] }

Create a new map schema (Map_Schema1) that includes only the source (Schema1/Table1) attributes contained in the matches mapping.
Output them in JSON format in the following structure:

{ "Map_Schema1": [ {"source": "Merged_Schema.attr_name", "target":"Schema1.attr_name"}]}

Create a new map schema (Map_Schema2) that includes only the target (Schema2/Table2) attributes contained in the matches mapping.
Output them in JSON format in the following structure:

{ "Map_Schema2": [ {"source": "Merged_Schema.attr_name", "target":"Schema2.attr_name"}]}

If no valid matches exist, return: {"Merged_Schema":[]}""",
                "ensemble": """You are an ensemble aggregator for multi-step schema processing results.

You have been given 3 independent responses for the same schema operation. Your task is to analyze these responses and create a single, high-quality merged result that combines the best aspects of all three responses.

ENSEMBLE AGGREGATION INSTRUCTIONS:
1. Compare the three responses carefully
2. Look for consensus across responses - matches/mappings that appear in multiple responses are likely correct
3. Use majority voting where applicable
4. For merge operations, combine unique valid entries from all responses
5. Maintain the exact same JSON structure as the individual responses
6. Ensure completeness - don't lose valid information from any response
7. Prioritize quality and accuracy over quantity

INPUT: Three independent responses labeled Response1, Response2, and Response3

Response1:
{response1}

Response2:
{response2}

Response3:
{response3}

OUTPUT: A single aggregated response following the exact same JSON structure as the input responses.

For matching operations, output:
{
  "matches": [...]
}

For merge/instance_merge operations, output:
{
  "Merged_Schema": [...],
  "Merged_Data": [...],
  "Map_Schema1": [...],
  "Map_Schema2": [...]
}

Apply ensemble logic to create the best possible aggregated result."""
            }
        }
    }
}

