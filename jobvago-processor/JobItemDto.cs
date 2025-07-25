using System.Text.Json.Serialization;

namespace Jobvago.Processor;

// This class maps directly to the JSON sent by the Python scraper.
// The JsonPropertyName attribute is used to match the Python snake_case style.
public class JobItemDto
{
    [JsonPropertyName("title")]
    public string Title { get; set; } = string.Empty;

    [JsonPropertyName("company_name")]
    public string CompanyName { get; set; } = string.Empty;

    [JsonPropertyName("location")]
    public string Location { get; set; } = string.Empty;

    [JsonPropertyName("raw_salary_text")]
    public string? RawSalaryText { get; set; }

    [JsonPropertyName("original_url")]
    public string OriginalUrl { get; set; } = string.Empty;

    [JsonPropertyName("source")]
    public string Source { get; set; } = string.Empty;
}