"""CSV management tools for Pydantic AI agent using best practices."""

import asyncio
import csv
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
from io import StringIO

import pandas as pd
from pydantic import BaseModel, Field, validator
from pydantic_ai import RunContext
from pydantic_ai.messages import ToolReturn, BinaryContent


# CSV sandboxed directory
CSV_BASE_DIR = Path("data/csv")


class CSVMetadata(BaseModel):
    """Metadata for CSV files."""
    filename: str
    rows: int
    columns: int
    size_bytes: int
    created_at: datetime
    last_modified: datetime
    column_names: List[str]
    column_types: Dict[str, str]


class CSVCreateRequest(BaseModel):
    """Request model for creating a new CSV file."""
    filename: str = Field(..., description="Name of the CSV file (without .csv extension)")
    data: List[Dict[str, Any]] = Field(..., description="List of dictionaries representing rows")
    overwrite: bool = Field(default=False, description="Whether to overwrite existing file")

    @validator('filename')
    def validate_filename(cls, v):
        # Remove any path separators for security
        return os.path.basename(v).replace('.csv', '')


class CSVReadRequest(BaseModel):
    """Request model for reading a CSV file."""
    filename: str = Field(..., description="Name of the CSV file (without .csv extension)")
    rows_limit: Optional[int] = Field(default=None, description="Maximum number of rows to return")
    columns: Optional[List[str]] = Field(default=None, description="Specific columns to read")

    @validator('filename')
    def validate_filename(cls, v):
        return os.path.basename(v).replace('.csv', '')


class CSVFilterRequest(BaseModel):
    """Request model for filtering CSV data."""
    filename: str = Field(..., description="Name of the CSV file")
    filters: Dict[str, Any] = Field(..., description="Column filters as key-value pairs")
    output_filename: Optional[str] = Field(default=None, description="Output file name for filtered data")

    @validator('filename', 'output_filename')
    def validate_filenames(cls, v):
        if v is None:
            return v
        return os.path.basename(v).replace('.csv', '')


class CSVSortRequest(BaseModel):
    """Request model for sorting CSV data."""
    filename: str = Field(..., description="Name of the CSV file")
    sort_by: str = Field(..., description="Column name to sort by")
    ascending: bool = Field(default=True, description="Sort in ascending order")
    output_filename: Optional[str] = Field(default=None, description="Output file name for sorted data")

    @validator('filename', 'output_filename')
    def validate_filenames(cls, v):
        if v is None:
            return v
        return os.path.basename(v).replace('.csv', '')


class CSVAggregateRequest(BaseModel):
    """Request model for aggregating CSV data."""
    filename: str = Field(..., description="Name of the CSV file")
    group_by: List[str] = Field(..., description="Columns to group by")
    agg_functions: Dict[str, str] = Field(..., description="Column aggregation functions (sum, mean, count, etc.)")
    output_filename: Optional[str] = Field(default=None, description="Output file name for aggregated data")

    @validator('filename', 'output_filename')
    def validate_filenames(cls, v):
        if v is None:
            return v
        return os.path.basename(v).replace('.csv', '')


class CSVOperationResult(BaseModel):
    """Result model for CSV operations."""
    success: bool
    message: str
    filename: Optional[str] = None
    rows_affected: Optional[int] = None
    metadata: Optional[CSVMetadata] = None
    data_preview: Optional[List[Dict[str, Any]]] = None


class CSVDependencies(BaseModel):
    """Dependencies for CSV tools."""
    user_id: Optional[str] = None
    request_id: Optional[str] = None
    max_file_size_mb: int = Field(default=50, description="Maximum file size in MB")
    max_rows: int = Field(default=100000, description="Maximum rows per file")

    class Config:
        arbitrary_types_allowed = True


def ensure_csv_directory() -> None:
    """Ensure the CSV directory exists."""
    CSV_BASE_DIR.mkdir(parents=True, exist_ok=True)


def get_safe_file_path(filename: str) -> Path:
    """Get a safe file path within the CSV directory."""
    ensure_csv_directory()
    # Sanitize filename and ensure it's within the sandbox
    safe_filename = os.path.basename(filename).replace('.csv', '') + '.csv'
    return CSV_BASE_DIR / safe_filename


def get_csv_metadata(file_path: Path) -> CSVMetadata:
    """Get metadata for a CSV file."""
    if not file_path.exists():
        raise FileNotFoundError(f"CSV file not found: {file_path}")
    
    # Read with pandas to get column info efficiently
    df = pd.read_csv(file_path, nrows=1)  # Just read header and first row
    full_df = pd.read_csv(file_path)  # Read all for row count
    
    stat = file_path.stat()
    
    return CSVMetadata(
        filename=file_path.name,
        rows=len(full_df),
        columns=len(df.columns),
        size_bytes=stat.st_size,
        created_at=datetime.fromtimestamp(stat.st_ctime),
        last_modified=datetime.fromtimestamp(stat.st_mtime),
        column_names=df.columns.tolist(),
        column_types={col: str(full_df[col].dtype) for col in df.columns}
    )


async def create_csv_file(
    ctx: RunContext[CSVDependencies], 
    request: CSVCreateRequest
) -> ToolReturn:
    """Create a new CSV file with the provided data."""
    try:
        file_path = get_safe_file_path(request.filename)
        
        # Check if file exists and overwrite is not allowed
        if file_path.exists() and not request.overwrite:
            return ToolReturn(
                return_value=CSVOperationResult(
                    success=False,
                    message=f"File {request.filename}.csv already exists. Use overwrite=True to replace it.",
                    filename=request.filename
                ).dict(),
                content=[f"❌ File creation failed: {request.filename}.csv already exists"]
            )
        
        # Validate data size
        if len(request.data) > ctx.deps.max_rows:
            return ToolReturn(
                return_value=CSVOperationResult(
                    success=False,
                    message=f"Data exceeds maximum rows limit: {ctx.deps.max_rows}",
                    filename=request.filename
                ).dict(),
                content=[f"❌ File creation failed: Too many rows ({len(request.data)} > {ctx.deps.max_rows})"]
            )
        
        # Create DataFrame and write to CSV
        df = pd.DataFrame(request.data)
        df.to_csv(file_path, index=False)
        
        # Get metadata
        metadata = get_csv_metadata(file_path)
        
        # Create preview (first 5 rows)
        preview = request.data[:5] if len(request.data) > 5 else request.data
        
        result = CSVOperationResult(
            success=True,
            message=f"Successfully created {request.filename}.csv with {len(request.data)} rows",
            filename=request.filename,
            rows_affected=len(request.data),
            metadata=metadata,
            data_preview=preview
        )
        
        return ToolReturn(
            return_value=result.dict(),
            content=[
                f"✅ Successfully created CSV file: {request.filename}.csv",
                f"📊 Rows: {len(request.data)}, Columns: {len(df.columns)}",
                f"📋 Columns: {', '.join(df.columns.tolist())}",
                f"🔍 Preview (first {len(preview)} rows):",
                f"```json\n{json.dumps(preview, indent=2, default=str)}\n```"
            ],
            metadata={
                "operation": "create_csv",
                "filename": request.filename,
                "user_id": ctx.deps.user_id,
                "timestamp": datetime.now().isoformat()
            }
        )
        
    except Exception as e:
        return ToolReturn(
            return_value=CSVOperationResult(
                success=False,
                message=f"Error creating CSV file: {str(e)}",
                filename=request.filename
            ).dict(),
            content=[f"❌ Error creating CSV file: {str(e)}"]
        )


async def read_csv_file(
    ctx: RunContext[CSVDependencies], 
    request: CSVReadRequest
) -> ToolReturn:
    """Read and return data from a CSV file."""
    try:
        file_path = get_safe_file_path(request.filename)
        
        if not file_path.exists():
            return ToolReturn(
                return_value=CSVOperationResult(
                    success=False,
                    message=f"CSV file not found: {request.filename}.csv",
                    filename=request.filename
                ).dict(),
                content=[f"❌ File not found: {request.filename}.csv"]
            )
        
        # Read CSV with specified parameters
        read_kwargs = {}
        if request.columns:
            read_kwargs['usecols'] = request.columns
        if request.rows_limit:
            read_kwargs['nrows'] = request.rows_limit
            
        df = pd.read_csv(file_path, **read_kwargs)
        data = df.to_dict('records')
        
        # Get metadata
        metadata = get_csv_metadata(file_path)
        
        result = CSVOperationResult(
            success=True,
            message=f"Successfully read {len(data)} rows from {request.filename}.csv",
            filename=request.filename,
            rows_affected=len(data),
            metadata=metadata,
            data_preview=data[:10] if len(data) > 10 else data  # Preview first 10 rows
        )
        
        # Create content for the model
        content_parts = [
            f"✅ Successfully read CSV file: {request.filename}.csv",
            f"📊 Returned {len(data)} rows" + (f" (limited from {metadata.rows} total)" if request.rows_limit and len(data) < metadata.rows else ""),
            f"📋 Columns: {', '.join(metadata.column_names)}"
        ]
        
        if len(data) <= 20:
            content_parts.extend([
                f"📄 Complete data:",
                f"```json\n{json.dumps(data, indent=2, default=str)}\n```"
            ])
        else:
            content_parts.extend([
                f"🔍 Preview (first 10 rows):",
                f"```json\n{json.dumps(data[:10], indent=2, default=str)}\n```",
                f"📁 Full data available in return value (access via tool result)"
            ])
        
        return ToolReturn(
            return_value=result.dict(),
            content=content_parts,
            metadata={
                "operation": "read_csv",
                "filename": request.filename,
                "rows_returned": len(data),
                "user_id": ctx.deps.user_id,
                "timestamp": datetime.now().isoformat()
            }
        )
        
    except Exception as e:
        return ToolReturn(
            return_value=CSVOperationResult(
                success=False,
                message=f"Error reading CSV file: {str(e)}",
                filename=request.filename
            ).dict(),
            content=[f"❌ Error reading CSV file: {str(e)}"]
        )


async def filter_csv_data(
    ctx: RunContext[CSVDependencies], 
    request: CSVFilterRequest
) -> ToolReturn:
    """Filter CSV data based on specified criteria."""
    try:
        file_path = get_safe_file_path(request.filename)
        
        if not file_path.exists():
            return ToolReturn(
                return_value=CSVOperationResult(
                    success=False,
                    message=f"CSV file not found: {request.filename}.csv",
                    filename=request.filename
                ).dict(),
                content=[f"❌ File not found: {request.filename}.csv"]
            )
        
        # Read CSV
        df = pd.read_csv(file_path)
        original_rows = len(df)
        
        # Apply filters
        for column, value in request.filters.items():
            if column in df.columns:
                if isinstance(value, str) and value.startswith('>='):
                    df = df[df[column] >= float(value[2:])]
                elif isinstance(value, str) and value.startswith('<='):
                    df = df[df[column] <= float(value[2:])]
                elif isinstance(value, str) and value.startswith('>'):
                    df = df[df[column] > float(value[1:])]
                elif isinstance(value, str) and value.startswith('<'):
                    df = df[df[column] < float(value[1:])]
                elif isinstance(value, str) and value.startswith('contains:'):
                    df = df[df[column].astype(str).str.contains(value[9:], na=False)]
                else:
                    df = df[df[column] == value]
        
        filtered_data = df.to_dict('records')
        
        # Save to output file if specified
        output_filename = request.output_filename or f"{request.filename}_filtered"
        if request.output_filename:
            output_path = get_safe_file_path(output_filename)
            df.to_csv(output_path, index=False)
        
        result = CSVOperationResult(
            success=True,
            message=f"Successfully filtered {request.filename}.csv: {original_rows} → {len(filtered_data)} rows",
            filename=output_filename if request.output_filename else request.filename,
            rows_affected=len(filtered_data),
            data_preview=filtered_data[:10] if len(filtered_data) > 10 else filtered_data
        )
        
        content_parts = [
            f"✅ Successfully filtered CSV data",
            f"📊 Results: {original_rows} → {len(filtered_data)} rows",
            f"🔍 Applied filters: {json.dumps(request.filters)}"
        ]
        
        if request.output_filename:
            content_parts.append(f"💾 Saved filtered data to: {output_filename}.csv")
        
        if len(filtered_data) <= 10:
            content_parts.extend([
                f"📄 Filtered data:",
                f"```json\n{json.dumps(filtered_data, indent=2, default=str)}\n```"
            ])
        else:
            content_parts.extend([
                f"🔍 Preview (first 10 rows):",
                f"```json\n{json.dumps(filtered_data[:10], indent=2, default=str)}\n```"
            ])
        
        return ToolReturn(
            return_value=result.dict(),
            content=content_parts,
            metadata={
                "operation": "filter_csv",
                "filename": request.filename,
                "filters_applied": request.filters,
                "rows_filtered": len(filtered_data),
                "user_id": ctx.deps.user_id,
                "timestamp": datetime.now().isoformat()
            }
        )
        
    except Exception as e:
        return ToolReturn(
            return_value=CSVOperationResult(
                success=False,
                message=f"Error filtering CSV file: {str(e)}",
                filename=request.filename
            ).dict(),
            content=[f"❌ Error filtering CSV file: {str(e)}"]
        )


async def sort_csv_data(
    ctx: RunContext[CSVDependencies], 
    request: CSVSortRequest
) -> ToolReturn:
    """Sort CSV data by specified column."""
    try:
        file_path = get_safe_file_path(request.filename)
        
        if not file_path.exists():
            return ToolReturn(
                return_value=CSVOperationResult(
                    success=False,
                    message=f"CSV file not found: {request.filename}.csv",
                    filename=request.filename
                ).dict(),
                content=[f"❌ File not found: {request.filename}.csv"]
            )
        
        # Read and sort CSV
        df = pd.read_csv(file_path)
        
        if request.sort_by not in df.columns:
            return ToolReturn(
                return_value=CSVOperationResult(
                    success=False,
                    message=f"Column '{request.sort_by}' not found in CSV file",
                    filename=request.filename
                ).dict(),
                content=[f"❌ Column '{request.sort_by}' not found. Available columns: {', '.join(df.columns)}"]
            )
        
        df_sorted = df.sort_values(by=request.sort_by, ascending=request.ascending)
        sorted_data = df_sorted.to_dict('records')
        
        # Save to output file if specified
        output_filename = request.output_filename or f"{request.filename}_sorted"
        if request.output_filename:
            output_path = get_safe_file_path(output_filename)
            df_sorted.to_csv(output_path, index=False)
        
        result = CSVOperationResult(
            success=True,
            message=f"Successfully sorted {request.filename}.csv by {request.sort_by} ({'ascending' if request.ascending else 'descending'})",
            filename=output_filename if request.output_filename else request.filename,
            rows_affected=len(sorted_data),
            data_preview=sorted_data[:10] if len(sorted_data) > 10 else sorted_data
        )
        
        content_parts = [
            f"✅ Successfully sorted CSV data",
            f"📊 Sorted by: {request.sort_by} ({'ascending' if request.ascending else 'descending'})",
            f"📋 Total rows: {len(sorted_data)}"
        ]
        
        if request.output_filename:
            content_parts.append(f"💾 Saved sorted data to: {output_filename}.csv")
        
        if len(sorted_data) <= 10:
            content_parts.extend([
                f"📄 Sorted data:",
                f"```json\n{json.dumps(sorted_data, indent=2, default=str)}\n```"
            ])
        else:
            content_parts.extend([
                f"🔍 Preview (first 10 rows):",
                f"```json\n{json.dumps(sorted_data[:10], indent=2, default=str)}\n```"
            ])
        
        return ToolReturn(
            return_value=result.dict(),
            content=content_parts,
            metadata={
                "operation": "sort_csv",
                "filename": request.filename,
                "sort_by": request.sort_by,
                "ascending": request.ascending,
                "user_id": ctx.deps.user_id,
                "timestamp": datetime.now().isoformat()
            }
        )
        
    except Exception as e:
        return ToolReturn(
            return_value=CSVOperationResult(
                success=False,
                message=f"Error sorting CSV file: {str(e)}",
                filename=request.filename
            ).dict(),
            content=[f"❌ Error sorting CSV file: {str(e)}"]
        )


async def aggregate_csv_data(
    ctx: RunContext[CSVDependencies], 
    request: CSVAggregateRequest
) -> ToolReturn:
    """Aggregate CSV data with grouping and functions."""
    try:
        file_path = get_safe_file_path(request.filename)
        
        if not file_path.exists():
            return ToolReturn(
                return_value=CSVOperationResult(
                    success=False,
                    message=f"CSV file not found: {request.filename}.csv",
                    filename=request.filename
                ).dict(),
                content=[f"❌ File not found: {request.filename}.csv"]
            )
        
        # Read CSV
        df = pd.read_csv(file_path)
        
        # Check if group_by columns exist
        missing_cols = [col for col in request.group_by if col not in df.columns]
        if missing_cols:
            return ToolReturn(
                return_value=CSVOperationResult(
                    success=False,
                    message=f"Group by columns not found: {missing_cols}",
                    filename=request.filename
                ).dict(),
                content=[f"❌ Group by columns not found: {missing_cols}. Available: {', '.join(df.columns)}"]
            )
        
        # Check if aggregation columns exist
        missing_agg_cols = [col for col in request.agg_functions.keys() if col not in df.columns]
        if missing_agg_cols:
            return ToolReturn(
                return_value=CSVOperationResult(
                    success=False,
                    message=f"Aggregation columns not found: {missing_agg_cols}",
                    filename=request.filename
                ).dict(),
                content=[f"❌ Aggregation columns not found: {missing_agg_cols}. Available: {', '.join(df.columns)}"]
            )
        
        # Perform aggregation
        df_agg = df.groupby(request.group_by).agg(request.agg_functions).reset_index()
        
        # Flatten column names if needed (for multi-level columns)
        if isinstance(df_agg.columns, pd.MultiIndex):
            df_agg.columns = ['_'.join(col).strip('_') for col in df_agg.columns.values]
        
        aggregated_data = df_agg.to_dict('records')
        
        # Save to output file if specified
        output_filename = request.output_filename or f"{request.filename}_aggregated"
        if request.output_filename:
            output_path = get_safe_file_path(output_filename)
            df_agg.to_csv(output_path, index=False)
        
        result = CSVOperationResult(
            success=True,
            message=f"Successfully aggregated {request.filename}.csv: {len(df)} → {len(aggregated_data)} rows",
            filename=output_filename if request.output_filename else request.filename,
            rows_affected=len(aggregated_data),
            data_preview=aggregated_data
        )
        
        content_parts = [
            f"✅ Successfully aggregated CSV data",
            f"📊 Results: {len(df)} → {len(aggregated_data)} rows",
            f"🔍 Grouped by: {', '.join(request.group_by)}",
            f"📈 Aggregations: {json.dumps(request.agg_functions)}"
        ]
        
        if request.output_filename:
            content_parts.append(f"💾 Saved aggregated data to: {output_filename}.csv")
        
        content_parts.extend([
            f"📄 Aggregated data:",
            f"```json\n{json.dumps(aggregated_data, indent=2, default=str)}\n```"
        ])
        
        return ToolReturn(
            return_value=result.dict(),
            content=content_parts,
            metadata={
                "operation": "aggregate_csv",
                "filename": request.filename,
                "group_by": request.group_by,
                "aggregations": request.agg_functions,
                "user_id": ctx.deps.user_id,
                "timestamp": datetime.now().isoformat()
            }
        )
        
    except Exception as e:
        return ToolReturn(
            return_value=CSVOperationResult(
                success=False,
                message=f"Error aggregating CSV file: {str(e)}",
                filename=request.filename
            ).dict(),
            content=[f"❌ Error aggregating CSV file: {str(e)}"]
        )


async def list_csv_files(ctx: RunContext[CSVDependencies]) -> ToolReturn:
    """List all CSV files in the sandboxed directory."""
    try:
        ensure_csv_directory()
        
        csv_files = list(CSV_BASE_DIR.glob("*.csv"))
        file_info = []
        
        for file_path in csv_files:
            try:
                metadata = get_csv_metadata(file_path)
                file_info.append({
                    "filename": metadata.filename,
                    "rows": metadata.rows,
                    "columns": metadata.columns,
                    "size_mb": round(metadata.size_bytes / 1024 / 1024, 2),
                    "last_modified": metadata.last_modified.isoformat(),
                    "column_names": metadata.column_names
                })
            except Exception as e:
                file_info.append({
                    "filename": file_path.name,
                    "error": f"Could not read file: {str(e)}"
                })
        
        result = CSVOperationResult(
            success=True,
            message=f"Found {len(csv_files)} CSV files",
            rows_affected=len(csv_files),
            data_preview=file_info
        )
        
        content_parts = [
            f"📁 CSV Files Directory: {CSV_BASE_DIR.absolute()}",
            f"📊 Found {len(csv_files)} CSV files"
        ]
        
        if file_info:
            content_parts.extend([
                f"📄 File details:",
                f"```json\n{json.dumps(file_info, indent=2, default=str)}\n```"
            ])
        else:
            content_parts.append("📂 Directory is empty - no CSV files found")
        
        return ToolReturn(
            return_value=result.dict(),
            content=content_parts,
            metadata={
                "operation": "list_csv_files",
                "files_found": len(csv_files),
                "user_id": ctx.deps.user_id,
                "timestamp": datetime.now().isoformat()
            }
        )
        
    except Exception as e:
        return ToolReturn(
            return_value=CSVOperationResult(
                success=False,
                message=f"Error listing CSV files: {str(e)}"
            ).dict(),
            content=[f"❌ Error listing CSV files: {str(e)}"]
        )


async def delete_csv_file(
    ctx: RunContext[CSVDependencies], 
    filename: str
) -> ToolReturn:
    """Delete a CSV file from the sandboxed directory."""
    try:
        # Sanitize filename
        safe_filename = os.path.basename(filename).replace('.csv', '')
        file_path = get_safe_file_path(safe_filename)
        
        if not file_path.exists():
            return ToolReturn(
                return_value=CSVOperationResult(
                    success=False,
                    message=f"CSV file not found: {safe_filename}.csv",
                    filename=safe_filename
                ).dict(),
                content=[f"❌ File not found: {safe_filename}.csv"]
            )
        
        # Get metadata before deletion
        metadata = get_csv_metadata(file_path)
        
        # Delete file
        file_path.unlink()
        
        result = CSVOperationResult(
            success=True,
            message=f"Successfully deleted {safe_filename}.csv",
            filename=safe_filename,
            metadata=metadata
        )
        
        return ToolReturn(
            return_value=result.dict(),
            content=[
                f"🗑️  Successfully deleted CSV file: {safe_filename}.csv",
                f"📊 File contained {metadata.rows} rows and {metadata.columns} columns"
            ],
            metadata={
                "operation": "delete_csv_file",
                "filename": safe_filename,
                "user_id": ctx.deps.user_id,
                "timestamp": datetime.now().isoformat()
            }
        )
        
    except Exception as e:
        return ToolReturn(
            return_value=CSVOperationResult(
                success=False,
                message=f"Error deleting CSV file: {str(e)}",
                filename=filename
            ).dict(),
            content=[f"❌ Error deleting CSV file: {str(e)}"]
        )
