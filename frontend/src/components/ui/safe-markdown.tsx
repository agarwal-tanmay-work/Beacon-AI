import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

/**
 * Markdown for text that may contain attacker-influenced content (AI replies that echo evidence, user messages).
 * Images are removed: a remote image URL would make the reader's browser send a request - a classic way to leak data
 * or confirm that a message was opened. Links open in a new tab without referrer / opener access.
 */
export function SafeMarkdown({ children }: { children: string }) {
    return (
        <ReactMarkdown
            remarkPlugins={[remarkGfm]}
            disallowedElements={["img"]}
            unwrapDisallowed
            components={{
                a: ({ href, children: linkChildren }) => (
                    <a href={href} target="_blank" rel="noopener noreferrer nofollow">
                        {linkChildren}
                    </a>
                ),
            }}
        >
            {children}
        </ReactMarkdown>
    );
}
