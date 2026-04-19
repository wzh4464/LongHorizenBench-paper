code pointer: https://github.com/facebookresearch/cca-swebench/blob/main/confucius/orchestrator/extensions/file/utils.py


def _get_matched_chunk(
    file_path: Path,
    find_lines: list[tuple[int, str]],
    file_lines: list[str],
    similarity_threshold: float,
) -> ChunkWithSimilarity:
    """Get the start and end indices of the matched lines in the file.

    (This function is used for the custom tag approach)

    Args:
        file_path (Path): The path to the file being searched.
        find_lines (list[tuple[int, str]]): A list of tuples where each tuple contains a line number and the corresponding line content to find.
        file_lines (list[str]): A list of strings representing the lines of the file content.
        similarity_threshold (float): The minimum similarity (0 to 1) to consider a match valid.

    Returns:
        ChunkWithSimilarity: The matched chunk. (similarity == 1.0)
    """

    # Verify find lines are consecutive
    for i in range(len(find_lines) - 1):
        if find_lines[i + 1][0] != find_lines[i][0] + 1:
            raise ValueError("Find lines must have consecutive line numbers")
    file_content = "\n".join(file_lines)
    find_text = "\n".join(content for _, content in find_lines)
    matched_chunks = find_matched_chunks_with_similarity(
        find_text=find_text,
        file_content=file_content,
        similarity_threshold=similarity_threshold,
    )

    occurrences = len(matched_chunks)

    if occurrences == 0:
        raise ValueError(
            f"No occurrence found in the file content and no similar part above the similarity threshold {similarity_threshold:.3f}. Please check the file content and try again."
        )

    if occurrences > 1:
        # found the chunk whose line numbers are the closest to the fine_lines line numbers
        matched_chunk = sorted(
            matched_chunks, key=lambda x: abs(x.start_line - find_lines[0][0])
        )[0]
        return matched_chunk

    assert occurrences == 1, "There should be exactly one occurrence at this point"
    matched_chunk = matched_chunks[0]
    if matched_chunk.similarity == 1.0:
        return matched_chunk

    matched_contents = view_file_content(
        content=file_content,
        start_line=matched_chunk.start_line,
        end_line=matched_chunk.end_line,
        max_view_lines=None,
        include_line_numbers=False,
    )
    matched_view = Tag(
        name="view",
        attributes={
            "start_line": str(matched_chunk.start_line),
            "end_line": str(matched_chunk.end_line),
            "file_path": str(file_path),
        },
        contents=view_file_content(
            content=file_content,
            start_line=matched_chunk.start_line,
            end_line=matched_chunk.end_line,
            max_view_lines=None,
        ),
    ).prettify()
    diff_patch = "\n".join(
        difflib.unified_diff(
            find_text.splitlines(),
            matched_contents.splitlines(),
            fromfile="find_text",
            tofile="matched_contents",
        )
    )
    raise ValueError(
        dedent(
            """\
        No exact occurrence found for the search string you provided.
        
        Closest match (similarity: {similarity}):
        {matched_view}
        
        Difference between expected and found text:
        ```
        {diff_patch}
        ```
        
        ACTION REQUIRED: Please update your `<find>` or `<find_after>` tag to match the exact content in the file with `<line_number>|<exact_line_content>` format.
        
        IMPORTANT: YOU MUST CONTINUE USING <file_edit> tag until successful. 
        DO NOT attempt alternative approaches such as:
        - Creating a new file to override the existing one
        - Using command line tools (e.g., `sed`, `awk`, etc.)
        
        Continue refining your `<find>` or `<find_after>` tag until it exactly matches the file content.
        """
        ).format(
            similarity=f"{matched_chunk.similarity:.3f}",
            matched_view=matched_view,
            diff_patch=diff_patch,
        )
    )